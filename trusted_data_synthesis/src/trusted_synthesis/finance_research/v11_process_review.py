"""Prospective CPU-only process/evidence/projection separation, not V10 relabeling.

The host binds existing text/IDs; it neither supplies semantic judgments nor
repairs old model responses. A binding is not proof of financial correctness.
"""

import copy
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import Episode, digest
from .qwen_protocol import strict_json_decoder
from .v6_task import public_trajectory_view

WIRE = "v11_decoupled_process_review.offline.v1"
DIMENSIONS = (
    "evidence_and_operations",
    "observation_interpretation",
    "unwithdrawn_critical_contradictions",
    "actual_revisions",
)
INTEGRITY_CHECKS = (
    "sealed",
    "calls_settled",
    "history_complete",
    "actions_observations_bound",
    "private_reference_isolated",
)
STATUSES = {"supported", "critical_error", "unknown", "not_applicable"}


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Reference(Record):
    id: str = Field(min_length=1)
    quote: str | None = None


class Assessment(Record):
    status: Literal["supported", "critical_error", "unknown", "not_applicable"]
    summary: str = Field(min_length=1)
    evidence: list[Reference]


class CriticalProcess(Record):
    evidence_and_operations: Assessment
    observation_interpretation: Assessment
    unwithdrawn_critical_contradictions: Assessment
    actual_revisions: Assessment


class Behavior(Record):
    description: str = Field(min_length=1)
    evidence: list[Reference] = Field(min_length=1)


class Supervision(Record):
    status: Literal["complete", "unknown"]
    positive_content: list[Reference]
    positive_actions: list[str]
    # Optional diagnostics, never an obligation to enumerate unapproved history.
    context_only: list[Reference] = Field(default_factory=list)


class AOutput(Record):
    process: CriticalProcess
    behavior: Behavior | None = None
    supervision: Supervision


class BOutput(Record):
    process: CriticalProcess


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _bound(value):
    return {**value, "id": digest(value)}


def policy_definition():
    return _bound(
        dict(
            schema="v11_decoupled_process_policy.v1",
            model="deepseek-flash",
            status="prospective_cpu_contract_only",
            production_authorized=False,
            previous_judgments_reclassified=False,
            host_semantic_repair=False,
            layers=[
                "raw_process_claims",
                "critical_evidence_binding",
                "auxiliary_projection",
                "candidate_admissibility",
            ],
            supervision_authority="A_only",
            B_has_supervision=False,
            behavior_is_not_a_process_or_pair_gate=True,
            omitted_content="unreviewed_zero_target_context",
            whole_action=(
                "model selects actual action_id; host binds successful event "
                "and complete original arguments"
            ),
            partial_quote=(
                "unique exact occurrence in its original segment; no fuzzy/normalized matching"
            ),
            partial_quote_semantic_completeness_proved=False,
            no_per_package_reason_minimum=True,
            all_pool_reason_masked_blocks_training_candidate=True,
            actual_training_requires=(
                "paid provenance, full fixed pool, native, paired process, "
                "state/chi, encoding and registered experiment gates"
            ),
        )
    )


def rubric(role):
    base = """Assess the actual complete public solving history, not a reconstructed proof.
Make the same four critical process assessments: evidence_and_operations,
observation_interpretation, unwithdrawn_critical_contradictions, actual_revisions.
supported/critical_error/unknown/not_applicable are your claims, not host-proved truth.
evidence_and_operations and unwithdrawn_critical_contradictions cannot be N/A.
A supported evidence_and_operations judgment and every critical_error need actual
evidence. An unresolved critical issue stays unknown. Initial public sources are
already visible; no read_source, forced checking, error, revision, graph or author
program match is required. Tool success alone does not establish sound reasoning.

Choose supplied unit/segment/action/event IDs. No start/end offsets are requested.
quote=null selects the complete original object. Prefer whole unit IDs. If a partial
quote is necessary, copy one contiguous exact substring uniquely present in the
original segment. The full original context remains visible; exact matching does
not prove that you preserved semantic qualifiers. Do not normalize numbers or text.
Never remove wrong or withdrawn earlier history. Consider the actual chronology.
"""
    if role == "B":
        return (
            base + "\nReturn only process. Do not produce supervision, masks "
            "or another reviewer's judgment."
        )
    return (
        base
        + """
Return process separately from optional behavior and supervision. behavior is an
auxiliary description, not an additional critical process test. Supervision lists
only explicitly approved original public-content references and actual action_ids.
Approved actions must really have a successful event; host will include their whole
original argument strings. Sources/observations cannot be targets. Unlisted text
and actions are unreviewed zero-target context, not silently approved. You need not
enumerate context_only: omit it or use an empty list. No per-package reason quota.
Use supervision.status=unknown if the projection cannot be completed confidently.
"""
    )


def _catalog(view):
    units = []
    for segment in view["segments"]:
        text = segment["text"]
        parts = (
            [text]
            if segment["kind"] in {"action_arguments", "source_table_cell", "unparsed_tool_call"}
            else text.splitlines(keepends=True) or [""]
        )
        _require("".join(parts) == text, "unit segmentation lost original characters")
        start = 0
        for part in parts:
            units.append(
                dict(
                    unit_id=f"u{len(units):05d}",
                    segment_id=segment["segment_id"],
                    kind=segment["kind"],
                    start=start,
                    end=start + len(part),
                    text=part,
                )
            )
            start += len(part)
    return dict(
        units=units,
        actions=[copy.deepcopy(a) for t in view["turns"] for a in t["actions"]],
        events=copy.deepcopy(view["events"]),
    )


def _payload(view, catalog, role):
    # Text appears once, in full-coverage physical units; host-only coordinates are omitted.
    public = copy.deepcopy(view)
    public["segments"] = [
        {
            **{k: v for k, v in s.items() if k not in {"text", "start", "end"}},
            "unit_ids": [
                u["unit_id"] for u in catalog["units"] if u["segment_id"] == s["segment_id"]
            ],
        }
        for s in view["segments"]
    ]
    public["units"] = [
        {k: v for k, v in u.items() if k not in {"start", "end"}} for u in catalog["units"]
    ]
    return dict(wire_protocol=WIRE, role=role, trajectory=public)


def output_schema(role, view, catalog):
    schema = (AOutput if role == "A" else BOutput).model_json_schema()
    ids = [u["unit_id"] for u in catalog["units"]] + [s["segment_id"] for s in view["segments"]]
    ids += [a["action_id"] for a in catalog["actions"]] + [e["event_id"] for e in catalog["events"]]
    schema["$defs"]["Reference"]["properties"]["id"]["enum"] = ids
    if role == "A" and catalog["actions"]:
        schema["$defs"]["Supervision"]["properties"]["positive_actions"]["items"]["enum"] = [
            a["action_id"] for a in catalog["actions"]
        ]
    return schema


def prepare_review_request(episode: Episode, *, slot_id, role, native_result, integrity):
    _require(
        role in {"A", "B"} and isinstance(slot_id, str) and slot_id,
        "original slot and A/B role required",
    )
    _require(
        isinstance(native_result, dict)
        and isinstance(integrity, dict)
        and all(
            k in integrity and (type(integrity[k]) is bool or integrity[k] is None)
            for k in INTEGRITY_CHECKS
        ),
        "separate native outcome and explicit integrity checks required",
    )
    view = public_trajectory_view(episode, slot_id=slot_id)
    catalog = _catalog(view)
    messages = [
        dict(role="system", content=rubric(role)),
        dict(
            role="user",
            content=json.dumps(
                _payload(view, catalog, role),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        ),
    ]
    return _bound(
        dict(
            schema="v11_process_review_request.v1",
            wire_protocol=WIRE,
            model="deepseek-flash",
            role=role,
            slot_id=slot_id,
            episode_sha256=digest(episode),
            trajectory=view,
            catalog=catalog,
            policy=policy_definition(),
            native_result=copy.deepcopy(native_result),
            integrity=copy.deepcopy(integrity),
            messages=messages,
            messages_sha256=digest(messages),
            output_schema=output_schema(role, view, catalog),
            production_authorized=False,
            native_or_private_reference_visible=False,
        )
    )


def _checked_request(request):
    _require(
        request.get("id") == digest({k: v for k, v in request.items() if k != "id"})
        and request.get("schema") == "v11_process_review_request.v1"
        and request.get("wire_protocol") == WIRE
        and request.get("model") == "deepseek-flash"
        and request.get("policy") == policy_definition()
        and request.get("role") in {"A", "B"},
        "not this bound prospective V11 request",
    )
    view, role = request["trajectory"], request["role"]
    _require(
        view["view_id"]
        == "public_trajectory:" + digest({k: v for k, v in view.items() if k != "view_id"})
        and view["episode_sha256"] == request["episode_sha256"]
        and view["slot_id"] == request["slot_id"],
        "original public trajectory identity changed",
    )
    catalog = _catalog(view)
    messages = [
        dict(role="system", content=rubric(role)),
        dict(
            role="user",
            content=json.dumps(
                _payload(view, catalog, role),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        ),
    ]
    _require(
        request["catalog"] == catalog
        and request["messages"] == messages
        and request["messages_sha256"] == digest(messages)
        and request["output_schema"] == output_schema(role, view, catalog),
        "host catalog/schema/messages changed",
    )
    return view, catalog


def _locate(reference, view, catalog, *, allow_empty=False):
    ref = Reference.model_validate(reference)
    documents = {d["segment_id"]: d for d in view["segments"]}
    unit = next((u for u in catalog["units"] if u["unit_id"] == ref.id), None)
    if unit is not None:
        segment_id, start, end = unit["segment_id"], unit["start"], unit["end"]
    else:
        aliases = {a["action_id"]: a["arguments_segment_id"] for a in catalog["actions"]}
        aliases.update({e["event_id"]: e["observation_segment_id"] for e in catalog["events"]})
        segment_id = aliases.get(ref.id, ref.id)
        _require(segment_id in documents, "reference_id_absent")
        start, end = 0, len(documents[segment_id]["text"])
    doc = documents[segment_id]
    if ref.quote is not None:
        _require(bool(ref.quote), "empty_partial_quote")
        found, offset = [], doc["text"].find(ref.quote)
        while offset >= 0 and len(found) < 2:
            found.append(offset)
            offset = doc["text"].find(ref.quote, offset + 1)
        _require(len(found) == 1, "partial_quote_absent_or_not_unique")
        left, right = found[0], found[0] + len(ref.quote)
        _require(start <= left < right <= end, "partial_quote_outside_selected_unit")
        start, end = left, right
    _require(allow_empty or start < end, "empty_reference_not_evidence_or_target")
    return dict(
        segment_id=segment_id,
        kind=doc["kind"],
        start=start,
        end=end,
        quote=doc["text"][start:end],
        selected_id=ref.id,
        binding="host_exact_original",
        semantic_scope_preserved_proved=False,
    )


def _reduce(statuses):
    return (
        "invalid"
        if "critical_error" in statuses
        else "unknown"
        if "unknown" in statuses
        else "valid"
    )


def _process(raw, view, catalog):
    values = raw if isinstance(raw, dict) else {}
    statuses = {
        k: values.get(k, {}).get("status") if isinstance(values.get(k), dict) else None
        for k in DIMENSIONS
    }
    readable = all(isinstance(v, str) and v in STATUSES for v in statuses.values())
    reducible = readable and all(
        statuses[k] != "not_applicable"
        for k in ("evidence_and_operations", "unwithdrawn_critical_contradictions")
    )
    claims = dict(
        raw=copy.deepcopy(raw),
        declared_statuses=statuses,
        readable=readable,
        declared_outcome=_reduce(statuses.values()) if reducible else None,
        semantic_truth_proved=False,
    )
    dimensions = {}
    for name in DIMENSIONS:
        try:
            value = Assessment.model_validate(values.get(name))
            _require(
                name not in {"evidence_and_operations", "unwithdrawn_critical_contradictions"}
                or value.status != "not_applicable",
                "critical_dimension_cannot_be_NA",
            )
            if (
                name == "evidence_and_operations" and value.status == "supported"
            ) or value.status == "critical_error":
                _require(bool(value.evidence), "critical_support_or_error_requires_evidence")
            evidence = [_locate(r.model_dump(), view, catalog) for r in value.evidence]
            dimensions[name] = dict(
                binding_status="bound", claimed_status=value.status, evidence=evidence, error=None
            )
        except (ValueError, TypeError, KeyError) as exc:
            dimensions[name] = dict(
                binding_status="failed", claimed_status=statuses[name], evidence=[], error=str(exc)
            )
    complete = set(values) == set(DIMENSIONS) and all(
        d["binding_status"] == "bound" for d in dimensions.values()
    )
    return claims, dict(
        dimensions=dimensions,
        all_critical_evidence_bound=complete,
        validated_process_outcome=_reduce(statuses.values()) if complete else "unknown",
        semantic_truth_proved=False,
        host_performed_financial_rejudgment=False,
    )


def _behavior(raw, view, catalog):
    if raw is None:
        return dict(status="not_supplied", raw=None, evidence=[], error=None)
    try:
        value = Behavior.model_validate(raw)
        evidence = [_locate(r.model_dump(), view, catalog) for r in value.evidence]
        return dict(status="bound", raw=copy.deepcopy(raw), evidence=evidence, error=None)
    except (ValueError, TypeError, KeyError) as exc:
        return dict(status="failed", raw=copy.deepcopy(raw), evidence=[], error=str(exc))


def _projection(raw, view, catalog):
    result = dict(
        raw=copy.deepcopy(raw),
        status="failed",
        usable=False,
        error=None,
        positive_content=[],
        positive_actions=[],
        context_only=[],
        omitted_are_zero_target=True,
    )
    try:
        value = Supervision.model_validate(raw)
        content = [_locate(r.model_dump(), view, catalog) for r in value.positive_content]
        context = [
            _locate(r.model_dump(), view, catalog, allow_empty=True) for r in value.context_only
        ]
        intervals = {}
        for item in content + context:
            _require(item["kind"] == "public_content", "only_public_content_for_content_projection")
            for left, right in intervals.get(item["segment_id"], []):
                _require(
                    item["end"] <= left or right <= item["start"],
                    "overlapping_projection_decisions",
                )
            intervals.setdefault(item["segment_id"], []).append((item["start"], item["end"]))
        _require(
            len(value.positive_actions) == len(set(value.positive_actions)),
            "duplicate_approved_action",
        )
        actions = {a["action_id"]: a for a in catalog["actions"]}
        events = {e["event_id"]: e for e in catalog["events"]}
        approved = []
        for action_id in value.positive_actions:
            _require(action_id in actions, "actual_action_id_absent")
            action = actions[action_id]
            event = events.get(action["event_id"])
            _require(
                event is not None
                and event["action_id"] == action_id
                and event["name"] == action["name"]
                and event["is_error"] is False,
                "positive_action_requires_actual_success",
            )
            span = _locate(dict(id=action_id), view, catalog)
            approved.append(
                dict(action_id=action_id, event_id=event["event_id"], whole_original_arguments=span)
            )
        result.update(
            status=value.status,
            usable=value.status == "complete",
            positive_content=content,
            positive_actions=approved,
            context_only=context,
        )
    except (ValueError, TypeError, KeyError) as exc:
        result["error"] = str(exc)
    return result


def inspect_review(raw, request):
    view, catalog = _checked_request(request)
    _require(isinstance(raw, str), "retain original review text, never a repaired dict")
    decoded, envelope_error = {}, None
    try:
        decoded = strict_json_decoder().decode(raw)
        _require(isinstance(decoded, dict), "review_must_be_an_object")
    except (ValueError, TypeError) as exc:
        decoded, envelope_error = {}, str(exc)
    allowed = {"process", "behavior", "supervision"} if request["role"] == "A" else {"process"}
    extra = sorted(set(decoded) - allowed)
    if extra:
        envelope_error = "unexpected top-level fields: " + ",".join(extra)
    claims, process = _process(decoded.get("process"), view, catalog)
    behavior = (
        _behavior(decoded.get("behavior"), view, catalog)
        if request["role"] == "A"
        else dict(status="not_applicable", raw=None)
    )
    projection = (
        _projection(decoded.get("supervision"), view, catalog)
        if request["role"] == "A"
        else dict(status="not_applicable", usable=False, raw=None)
    )
    raw_chars = sum(len(d["text"]) for d in view["segments"] if d["kind"] == "public_content")
    positive_chars = (
        sum(s["end"] - s["start"] for s in projection.get("positive_content", []))
        if projection["usable"]
        else None
    )
    integrity = all(request["integrity"][k] is True for k in INTEGRITY_CHECKS)
    blockers = []
    if envelope_error:
        blockers.append("review_envelope_invalid")
    if process["validated_process_outcome"] != "valid":
        blockers.append("validated_process_not_valid")
    if not integrity:
        blockers.append("original_integrity_not_verified")
    if request["role"] == "A" and not projection["usable"]:
        blockers.append("A_supervision_projection_unavailable")
    return _bound(
        dict(
            schema="v11_decoupled_process_inspection.v1",
            request=copy.deepcopy(request),
            request_id=request["id"],
            role=request["role"],
            slot_id=request["slot_id"],
            episode_sha256=request["episode_sha256"],
            raw_review=raw,
            raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            envelope_error=envelope_error,
            raw_process_claims=claims,
            process_evidence_binding=process,
            auxiliary=dict(behavior=behavior, supervision=projection),
            reason_projection=dict(
                raw_public_characters=raw_chars,
                positive_public_characters=positive_chars,
                all_public_reasoning_masked=(raw_chars > 0 and positive_chars == 0)
                if positive_chars is not None
                else None,
            )
            if request["role"] == "A"
            else None,
            training_admissibility=dict(
                candidate_gate=not blockers,
                blockers=blockers,
                production_admitted=False,
                single_package_reason0_is_not_an_exclusion=True,
            ),
            semantic_truth_proved=False,
            historical_judgments_reclassified=False,
            actual_model_call_receipt_verified=False,
            annotation_origin="prospective_CPU_contract_only",
        )
    )


def _checked_inspection(value):
    _require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"})
        and value.get("schema") == "v11_decoupled_process_inspection.v1",
        "not a V11 prospective inspection",
    )
    _require(
        inspect_review(value["raw_review"], value["request"]) == value,
        "inspection must reproduce from its own raw response",
    )
    return value


def resolve_candidate_pair(a, b, *, q_native):
    a, b = _checked_inspection(a), _checked_inspection(b)
    _require(
        a["role"] == "A"
        and b["role"] == "B"
        and a["slot_id"] == b["slot_id"]
        and a["episode_sha256"] == b["episode_sha256"]
        and a["request"]["trajectory"] == b["request"]["trajectory"]
        and a["request"]["native_result"] == b["request"]["native_result"],
        "same original isolated A/B pair required",
    )
    metric = a["request"]["native_result"].get("native", {}).get("execution_accuracy")
    _require(
        metric is None or (type(metric) in (int, float, bool) and metric in (0, 1)),
        "native result must remain binary or unknown",
    )
    _require(
        q_native is (None if metric is None else bool(metric)),
        "pair native flag differs from its separate retained result",
    )
    joint = q_native is True and all(
        v["process_evidence_binding"]["validated_process_outcome"] == "valid" for v in (a, b)
    )
    return _bound(
        dict(
            schema="v11_candidate_pair.v1",
            slot_id=a["slot_id"],
            A=a,
            B=b,
            q_native=q_native,
            joint_process_candidate=joint,
            candidate_gate=joint
            and all(v["training_admissibility"]["candidate_gate"] for v in (a, b)),
            supervision_authority="A",
            production_admitted=False,
            pending_actual_gates=[
                "paid_provenance",
                "complete_fixed_candidate_pool",
                "state_chi_and_nontrivial_support",
                "student_encoding",
                "registered_training",
            ],
            same_model_isolated_contexts_not_independent_experts=True,
        )
    )


def candidate_pool_check(pairs):
    _require(len({p["slot_id"] for p in pairs}) == len(pairs), "duplicate candidate slot")
    for pair in pairs:
        _require(
            resolve_candidate_pair(pair["A"], pair["B"], q_native=pair["q_native"]) == pair,
            "candidate pair changed",
        )
    required = [p for p in pairs if p["joint_process_candidate"]]
    blocked = [p["slot_id"] for p in required if not p["candidate_gate"]]
    raw_chars = sum(p["A"]["reason_projection"]["raw_public_characters"] for p in required)
    projection_counts_known = all(
        p["A"]["reason_projection"]["positive_public_characters"] is not None for p in required
    )
    reason_chars = (
        sum(p["A"]["reason_projection"]["positive_public_characters"] for p in required)
        if projection_counts_known
        else None
    )
    all_reason_zero = (
        bool(required) and raw_chars > 0 and reason_chars == 0 if projection_counts_known else None
    )
    return _bound(
        dict(
            schema="v11_candidate_pool_check.v1",
            input_slot_ids=[p["slot_id"] for p in pairs],
            candidate_slot_ids=[p["slot_id"] for p in required],
            blocked_slot_ids=blocked,
            no_joint_process_candidate_dropped=True,
            no_reason0_package_dropped=True,
            all_pool_public_reasoning_masked=all_reason_zero,
            projection_pool_candidate_gate=bool(required)
            and not blocked
            and all_reason_zero is False,
            production_admitted=False,
            original_fixed_denominator_completeness_checked=False,
            state_chi_and_encoding_checked=False,
        )
    )
