"""Frozen production A/B process reviews and ONE whole-task semantic mapping.

No model call here. A alone supplies supervision; B never sees A, native/gold or
produces a competing mask. State ambiguity is not a financial invalidity verdict.
"""

from __future__ import annotations

import json
import math
from typing import Literal

from pydantic import Field

from .contracts import digest
from .qwen_protocol import strict_json_decoder
from .v10_process_review import (
    CriticalProcess,
    Locator,
    Record,
    bound,
    inspect_process_review,
    prepare_process_request,
    require,
    supervision_manifest,
)
from .v10_process_review import policy_definition as process_policy

REVIEW_WIRE = "v10_production_process_AB.v1"
MAPPING_WIRE = "v10_once_task_semantic_mapping.v1"
CAPS = (2048, 4096, 8192, 16384, 32768, 65536)


class BOutput(Record):
    process: CriticalProcess


class SlotLocator(Locator):
    slot_id: str


class Intervention(Record):
    slot_id: str
    kind: Literal["verification", "revision"]
    action_id: str
    observation_segment_id: str
    consequence: Locator
    effect: str = Field(min_length=1)


class SemanticState(Record):
    state_id: str = Field(min_length=1)
    slot_ids: list[str] = Field(min_length=1)
    semantic_summary: str = Field(min_length=1)
    evidence: list[SlotLocator] = Field(min_length=1)
    chi: Literal[0, 1]
    chi_reason: str = Field(min_length=1)
    interventions: list[Intervention]


class Ambiguity(Record):
    slot_ids: list[str] = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: list[SlotLocator]


class MappingOutput(Record):
    mapping_status: Literal["complete", "unknown"]
    states: list[SemanticState]
    ambiguities: list[Ambiguity]


def review_policy_definition():
    return bound(
        dict(
            schema="v10_production_AB_and_once_mapping_policy.v1",
            model="deepseek-flash",
            process_policy_id=process_policy()["id"],
            A="four process checks, compact behavior, unique supervision spans",
            B="independent four process checks only; no second behavior or mask",
            joint="native execution true AND A/B annotation_succeeded/process valid",
            supervision_authority="A fixed before results; never choose a more favorable side",
            process_review_native_gold_and_other_side_visible=False,
            task_mapping="one complete semantic partition of ALL jointly valid originals",
            semantic_state_basis=[
                "evidence selection",
                "derivation",
                "observation understanding",
                "consequential verification or revision",
            ],
            chi=(
                "actual consequential verification/revision with original action, "
                "observation and later evidence"
            ),
            hash_length_tool_pattern_state_classification=False,
            ambiguous_mapping_is_not_process_invalid=True,
            ambiguous_package_drop_or_automatic_singleton=False,
            all_joint_packages_must_map_and_encode=True,
            zero_native_support_task_stops_batch_or_conditional_training=False,
            original_task_denominator=1000,
            original_slot_denominator=8000,
            old_stock_splicing=False,
            paid_pilot=False,
            retries=0,
            concurrency=8,
            transport=dict(trust_env=False, verify_tls=True, retries=0),
            capacity=dict(
                allowed_max_tokens=list(CAPS),
                multiplier="5/4 ceiling then next fixed tier",
                A="1024 + original_model_characters/2 + 48*turns + 64*actions",
                B="768 + original_model_characters/8 + 32*turns + 24*actions",
                mapping="1024 + original_model_characters/8 + 256*packages + 96*turns",
                original_model_characters=(
                    "public_content plus original action_arguments, not source length"
                ),
                response_tokens_forecast_exact=False,
                over_maximum="stop; no clipping or retry enlargement",
            ),
            actual_API_receipt_required=True,
            finite_checks_do_not_prove_financial_semantics=True,
            SFT_mask_is_not_feedback_probability_domain=True,
        )
    )


def capacity(stage, views):
    chars = sum(
        len(d["text"])
        for v in views
        for d in v["segments"]
        if d["kind"] in {"public_content", "action_arguments"}
    )
    turns = sum(len(v["turns"]) for v in views)
    actions = sum(len(t["actions"]) for v in views for t in v["turns"])
    if stage == "A":
        load = 1024 + chars / 2 + 48 * turns + 64 * actions
    elif stage == "B":
        load = 768 + chars / 8 + 32 * turns + 24 * actions
    elif stage == "mapping":
        load = 1024 + chars / 8 + 256 * len(views) + 96 * turns
    else:
        raise ValueError("unknown fixed capacity stage")
    estimate = math.ceil(1.25 * load)
    cap = next((n for n in CAPS if n >= estimate), None)
    require(
        cap is not None, "original workload exceeds frozen maximum; no clipping or enlarged retry"
    )
    return dict(
        stage=stage,
        original_model_characters=chars,
        turns=turns,
        actions=actions,
        packages=len(views),
        estimated_output_requirement=estimate,
        max_output_tokens=cap,
        exact_token_forecast=False,
    )


def _tool(model):
    schema = model.model_json_schema()
    definitions = schema.get("$defs", {})

    def inline(value):
        if "$ref" in value:
            return inline(definitions[value["$ref"].removeprefix("#/$defs/")])
        out = {k: value[k] for k in ("type", "enum") if k in value}
        if value.get("type") == "object":
            props = {k: inline(v) for k, v in value["properties"].items()}
            out.update(properties=props, required=list(props), additionalProperties=False)
        elif value.get("type") == "array":
            out["items"] = inline(value["items"])
        return out

    return dict(
        type="function", function=dict(name="submit_review", strict=True, parameters=inline(schema))
    )


def b_rubric():
    return """Independently review this actual public FinQA trajectory. You do not see
another review, benchmark correctness, gold or private reference. Return ONLY the four
critical process assessments: evidence_and_operations, observation_interpretation,
unwithdrawn_critical_contradictions, actual_revisions. Each is status/summary/evidence.
Use supported, critical_error, unknown, or not_applicable. evidence_and_operations
requires necessary exact original evidence when supported and cannot be not_applicable.
For unwithdrawn_critical_contradictions, supported means checked and no critical
unwithdrawn contradiction; critical_error means one exists; unknown means unresolved.
That dimension cannot be not_applicable. Observations/revisions may be not_applicable
when absent or unnecessary. Critical errors need original locators; annotation doubt
or a critical mixed ambiguity remains unknown, not invalid.
Initial table/text are already visible, without mandatory read_source. Judge the
actual current program submission contract; no author DAG equivalence, answer/scale,
R/U/Q fields, fabricated verification, per-fragment proof graph or narration regex.
A tool result alone does not prove the financial choice correct. Withdrawn mistakes
and actual recovery or exploratory paths need not all support the final answer.
Do not produce behavior classes, supervision masks, target lists or an alternative
annotation. Two isolated same-model reviews are a design choice, not independent experts.
"""


def mapping_rubric():
    return """Map ALL supplied jointly process-valid original packages for ONE FinQA
task into semantic behavior states in ONE response. You see originals and A's concise
behavior description, not a target state count. Return mapping_status/states/ambiguities.
When complete, each original slot appears in exactly one state and no slot is omitted.
Use evidence choice, derivation structure, observation understanding and consequential
verification/revision to distinguish states. Surface wording, IDs/hashes, verbosity,
tool counts/order or direct/execute/error patterns alone do not define semantic states.
Do not compare all 28 pairs or manufacture a proof graph. Do not turn an ambiguous
package into a singleton or delete it; use mapping_status=unknown and locate the actual
ambiguity. Mapping uncertainty does not change its already retained process judgment.
state_id is just a local locator, never the criterion for semantic identity.
chi=1 only for actual substantive verification or revision that affected subsequent
acceptance/judgment. For EACH member of a chi=1 state give an intervention: actual
action_id, its observation_segment_id, a later exact original consequence location,
kind and a concise explanation of the information/acceptance change. A failed tool,
changed arguments, 'I checked', redundant arithmetic or an ordinary execution alone
is insufficient. chi=0 is legitimate even for long or multi-tool paths. States must
have one coherent chi; if the originals cannot establish this, retain mapping unknown.
An intervention consequence must be later public content or action arguments, not a
host-authored explanation or tool observation masquerading as the model's revision.
All approved originals remain in the common material kernel; never prefer short,
easy, novel or high-performing packages. This operation does not rescore native
answers, change A's one authoritative mask or prove financial semantics independently.
"""


def prepare_review_request(episode, *, slot_id, role, native_result, integrity, protocol_id):
    from .v10_budget import review_episode_id

    require(role in {"A", "B"}, "fixed A/B roles only")
    candidate = prepare_process_request(
        episode,
        slot_id=slot_id,
        native_result=native_result,
        integrity=integrity,
        reviewer=0 if role == "A" else 1,
    )
    view = candidate["trajectory"]
    cap = capacity(role, [view])
    if role == "A":
        messages, tool = candidate["messages"], candidate["strict_tool"]
    else:
        messages = [
            dict(role="system", content=b_rubric()),
            dict(
                role="user",
                content=json.dumps(
                    dict(trajectory=view, role="B"), ensure_ascii=False, separators=(",", ":")
                ),
            ),
        ]
        tool = _tool(BOutput)
    return bound(
        dict(
            schema="v10_production_review_request.v1",
            wire_protocol=REVIEW_WIRE,
            protocol_id=protocol_id,
            policy_id=review_policy_definition()["id"],
            model="deepseek-flash",
            role=role,
            slot_id=slot_id,
            task_id=episode.task_id,
            episode_id=review_episode_id(protocol_id, slot_id, role),
            episode_sha256=digest(episode),
            view_id=view["view_id"],
            candidate_request=candidate,
            messages=messages,
            strict_tool=tool,
            capacity=cap,
            max_output_tokens=cap["max_output_tokens"],
            native_and_gold_visible=False,
            other_reviewer_visible=False,
        )
    )


def _assess_b(raw, candidate):
    view = candidate["trajectory"]
    docs = {d["segment_id"]: d for d in view["segments"]}
    try:
        parsed = BOutput.model_validate(strict_json_decoder().decode(raw))
        checks = parsed.process.model_dump(mode="json")
        for name, check in checks.items():
            if name in {"evidence_and_operations", "unwithdrawn_critical_contradictions"}:
                require(check["status"] != "not_applicable", "critical dimension cannot be N/A")
            if check["status"] == "critical_error" or (
                name == "evidence_and_operations" and check["status"] == "supported"
            ):
                require(check["evidence"], "necessary critical evidence absent")
            for evidence in check["evidence"]:
                _located(evidence, docs)
        statuses = {c["status"] for c in checks.values()}
        validity = (
            "invalid"
            if "critical_error" in statuses
            else "unknown"
            if "unknown" in statuses
            else "valid"
        )
        return bound(
            dict(
                schema="v10_B_short_inspection.v1",
                review_status="annotation_succeeded",
                process_validity=validity,
                parsed=parsed.model_dump(mode="json"),
                error=None,
            )
        )
    except (ValueError, TypeError, KeyError) as error:
        return bound(
            dict(
                schema="v10_B_short_inspection.v1",
                review_status="annotation_failed",
                process_validity="unknown",
                parsed=None,
                error=f"{type(error).__name__}: {error}",
            )
        )


def _located(value, docs):
    d = docs.get(value["segment_id"])
    require(
        d is not None
        and type(value["start"]) is int
        and type(value["end"]) is int
        and 0 <= value["start"] < value["end"] <= len(d["text"])
        and d["text"][value["start"] : value["end"]] == value["quote"],
        "mapping/review locator is not exact original text",
    )
    return d


def checked_request(request):
    from .v10_budget import map_episode_id, review_episode_id

    require(
        request.get("id") == digest({k: v for k, v in request.items() if k != "id"}),
        "production request changed",
    )
    require(
        request.get("model") == "deepseek-flash"
        and request.get("policy_id") == review_policy_definition()["id"],
        "production model/policy changed",
    )
    if request.get("wire_protocol") == REVIEW_WIRE:
        candidate, role = request["candidate_request"], request["role"]
        from .v10_process_review import _checked_request

        view = _checked_request(candidate)
        require(
            role in {"A", "B"}
            and request["episode_id"]
            == review_episode_id(request["protocol_id"], request["slot_id"], role),
            "wrong fixed review job identity",
        )
        require(
            request["episode_sha256"] == candidate["episode_sha256"]
            and request["view_id"] == view["view_id"]
            and request["slot_id"] == view["slot_id"],
            "original slot binding differs",
        )
        expected_messages = (
            candidate["messages"]
            if role == "A"
            else [
                dict(role="system", content=b_rubric()),
                dict(
                    role="user",
                    content=json.dumps(
                        dict(trajectory=view, role="B"), ensure_ascii=False, separators=(",", ":")
                    ),
                ),
            ]
        )
        expected_tool = candidate["strict_tool"] if role == "A" else _tool(BOutput)
        cap = capacity(role, [view])
    elif request.get("wire_protocol") == MAPPING_WIRE:
        require(
            request["episode_id"] == map_episode_id(request["protocol_id"], request["task_id"]),
            "wrong fixed map job identity",
        )
        packages = request["packages"]
        require(
            packages
            and len(packages) <= 8
            and len({p["slot_id"] for p in packages}) == len(packages),
            "one original task package set required",
        )
        for p in packages:
            view = p["trajectory"]
            require(
                view["view_id"]
                == "public_trajectory:" + digest({k: v for k, v in view.items() if k != "view_id"})
                and view["slot_id"] == p["slot_id"]
                and view["task_id"] == request["task_id"],
                "mapping original view changed",
            )
        expected_messages = [
            dict(role="system", content=mapping_rubric()),
            dict(
                role="user",
                content=json.dumps(
                    dict(task_id=request["task_id"], packages=packages),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ),
        ]
        expected_tool, cap = (
            _tool(MappingOutput),
            capacity("mapping", [p["trajectory"] for p in packages]),
        )
    else:
        raise ValueError("unregistered V10 production wire")
    require(
        request["messages"] == expected_messages
        and request["strict_tool"] == expected_tool
        and request["capacity"] == cap
        and request["max_output_tokens"] == cap["max_output_tokens"],
        "fixed prompt/schema/original-load capacity changed",
    )
    return request


def review_record(request, artifact, ledger_record):
    from .v10_review_provider import validate_paid_artifact

    receipt = validate_paid_artifact(request, artifact, ledger_record)
    require(request["wire_protocol"] == REVIEW_WIRE, "not an A/B process review")
    normal = artifact["finish_reason"] == "tool_calls" and not artifact["review_format_error"]
    if request["role"] == "A":
        inspection = inspect_process_review(
            artifact["review_text"] if normal else "", request["candidate_request"]
        )
        manifest = supervision_manifest(inspection)
    else:
        inspection = _assess_b(
            artifact["review_text"] if normal else "", request["candidate_request"]
        )
        manifest = None
    return bound(
        dict(
            schema="v10_paid_process_review.v1",
            protocol_id=request["protocol_id"],
            policy_id=request["policy_id"],
            role=request["role"],
            slot_id=request["slot_id"],
            task_id=request["task_id"],
            episode_sha256=request["episode_sha256"],
            view_id=request["view_id"],
            review_status=inspection["review_status"],
            process_validity=inspection["process_validity"],
            inspection=inspection,
            supervision_manifest=manifest,
            request=request,
            artifact=artifact,
            ledger_binding=receipt,
            actual_model_call_receipt_verified=True,
            semantic_truth_proved=False,
            training_material_admitted=False,
        )
    )


def validate_review_record(record, ledger_record):
    require(
        review_record(record["request"], record["artifact"], ledger_record) == record,
        "paid process record must replay from original receipt, never self-reported valid",
    )
    return record


def resolve_joint_review(a, b, *, q_native):
    require(type(q_native) is bool or q_native is None, "native outcome cannot be inferred")
    for record, role in ((a, "A"), (b, "B")):
        require(
            record["id"] == digest({k: v for k, v in record.items() if k != "id"})
            and record["schema"] == "v10_paid_process_review.v1"
            and record["role"] == role
            and record["policy_id"] == review_policy_definition()["id"],
            "wrong original A/B production records",
        )
    require(
        all(
            a[k] == b[k] for k in ("protocol_id", "slot_id", "task_id", "episode_sha256", "view_id")
        ),
        "A/B must judge the same original package",
    )
    joint = q_native is True and all(
        r["review_status"] == "annotation_succeeded" and r["process_validity"] == "valid"
        for r in (a, b)
    )
    return bound(
        dict(
            schema="v10_joint_process_review.v1",
            protocol_id=a["protocol_id"],
            policy_id=a["policy_id"],
            slot_id=a["slot_id"],
            task_id=a["task_id"],
            episode_sha256=a["episode_sha256"],
            q_native=q_native,
            joint_valid=joint,
            A_record_id=a["id"],
            B_record_id=b["id"],
            A=a,
            B=b,
            A_manifest=a["supervision_manifest"],
            supervision_authority="A",
            process_labels_retained=dict(A=a["process_validity"], B=b["process_validity"]),
        )
    )


def prepare_mapping_request(*, task_id, joint_records, protocol_id):
    from .v10_budget import map_episode_id

    require(
        0 < len(joint_records) <= 8, "mapping requires all jointly valid originals for one task"
    )
    packages, bindings = [], []
    for joint in joint_records:
        require(
            joint == resolve_joint_review(joint["A"], joint["B"], q_native=joint["q_native"])
            and joint["joint_valid"]
            and joint["task_id"] == task_id
            and joint["protocol_id"] == protocol_id,
            "mapping accepts only real jointly valid same-batch packages",
        )
        packages.append(
            dict(
                slot_id=joint["slot_id"],
                trajectory=joint["A"]["request"]["candidate_request"]["trajectory"],
                behavior=joint["A"]["inspection"]["parsed"]["behavior"],
            )
        )
        bindings.append(
            dict(
                slot_id=joint["slot_id"],
                joint_record_id=joint["id"],
                A_record_id=joint["A_record_id"],
                B_record_id=joint["B_record_id"],
            )
        )
    cap = capacity("mapping", [p["trajectory"] for p in packages])
    messages = [
        dict(role="system", content=mapping_rubric()),
        dict(
            role="user",
            content=json.dumps(
                dict(task_id=task_id, packages=packages), ensure_ascii=False, separators=(",", ":")
            ),
        ),
    ]
    return bound(
        dict(
            schema="v10_production_mapping_request.v1",
            wire_protocol=MAPPING_WIRE,
            protocol_id=protocol_id,
            policy_id=review_policy_definition()["id"],
            model="deepseek-flash",
            role="mapping",
            task_id=task_id,
            episode_id=map_episode_id(protocol_id, task_id),
            packages=packages,
            joint_bindings=bindings,
            messages=messages,
            strict_tool=_tool(MappingOutput),
            capacity=cap,
            max_output_tokens=cap["max_output_tokens"],
            all_joint_packages_required=True,
        )
    )


def _inspect_mapping(raw, request):
    try:
        value = MappingOutput.model_validate(strict_json_decoder().decode(raw))
        packages = {p["slot_id"]: p["trajectory"] for p in request["packages"]}
        docs = {sid: {d["segment_id"]: d for d in v["segments"]} for sid, v in packages.items()}
        seen, state_ids = [], set()
        for state in value.states:
            require(state.state_id not in state_ids, "duplicate state locator")
            state_ids.add(state.state_id)
            require(
                len(set(state.slot_ids)) == len(state.slot_ids)
                and set(state.slot_ids) <= set(packages),
                "unknown/duplicate state member",
            )
            seen.extend(state.slot_ids)
            for ev in state.evidence:
                require(ev.slot_id in state.slot_ids, "state evidence must belong to its members")
                _located(ev.model_dump(), docs[ev.slot_id])
            demonstrated = set()
            for item in state.interventions:
                require(item.slot_id in state.slot_ids, "chi evidence belongs to another state")
                view = packages[item.slot_id]
                actions = {
                    a["action_id"]: (a, t["turn_index"])
                    for t in view["turns"]
                    for a in t["actions"]
                }
                require(
                    item.action_id in actions, "chi action was not executed in original package"
                )
                action, turn_index = actions[item.action_id]
                event = next(
                    (e for e in view["events"] if e["event_id"] == action["event_id"]), None
                )
                require(
                    event is not None
                    and event["observation_segment_id"] == item.observation_segment_id,
                    "chi requires the actual action/observation pair",
                )
                consequence = _located(item.consequence.model_dump(), docs[item.slot_id])
                require(
                    consequence["kind"] in {"public_content", "action_arguments"}
                    and consequence["turn_index"] > turn_index,
                    "chi consequence must be later actual model behavior",
                )
                demonstrated.add(item.slot_id)
            require(
                (state.chi == 1 and demonstrated == set(state.slot_ids))
                or (state.chi == 0 and not state.interventions),
                "chi cannot be inferred from one exemplar or tool count",
            )
        require(len(seen) == len(set(seen)), "one original package cannot be in two states")
        for ambiguity in value.ambiguities:
            require(
                set(ambiguity.slot_ids) <= set(packages), "ambiguity references a foreign package"
            )
            for ev in ambiguity.evidence:
                require(ev.slot_id in ambiguity.slot_ids, "ambiguity evidence mismatch")
                _located(ev.model_dump(), docs[ev.slot_id])
        if value.mapping_status == "complete":
            require(
                set(seen) == set(packages) and not value.ambiguities,
                "complete mapping must retain every jointly valid original",
            )
        else:
            require(
                value.ambiguities,
                "unknown mapping must describe ambiguity, not drop a hard package",
            )
        return dict(
            annotation_status="annotation_succeeded",
            mapping_status=value.mapping_status,
            parsed=value.model_dump(mode="json"),
            error=None,
        )
    except (ValueError, TypeError, KeyError) as error:
        return dict(
            annotation_status="annotation_failed",
            mapping_status="unknown",
            parsed=None,
            error=f"{type(error).__name__}: {error}",
        )


def mapping_record(request, artifact, ledger_record):
    from .v10_review_provider import validate_paid_artifact

    receipt = validate_paid_artifact(request, artifact, ledger_record)
    require(request["wire_protocol"] == MAPPING_WIRE, "not a task mapping")
    normal = artifact["finish_reason"] == "tool_calls" and not artifact["review_format_error"]
    result = _inspect_mapping(artifact["review_text"] if normal else "", request)
    complete = result["mapping_status"] == "complete"
    states = result["parsed"]["states"] if result["parsed"] else []
    return bound(
        dict(
            schema="v10_paid_task_mapping.v1",
            protocol_id=request["protocol_id"],
            policy_id=request["policy_id"],
            task_id=request["task_id"],
            **result,
            states=states,
            state_by_slot={sid: s["state_id"] for s in states for sid in s["slot_ids"]}
            if complete
            else {},
            chi_by_state={s["state_id"]: s["chi"] for s in states} if complete else {},
            joint_bindings=request["joint_bindings"],
            request=request,
            artifact=artifact,
            ledger_binding=receipt,
            mapping_admitted=complete,
            original_process_judgments_unchanged=True,
            no_ambiguous_package_dropped=True,
            actual_model_call_receipt_verified=True,
            semantic_truth_proved=False,
        )
    )


def validate_mapping_record(record, ledger_record):
    require(
        mapping_record(record["request"], record["artifact"], ledger_record) == record,
        "paid mapping record must replay from its original receipt",
    )
    return record
