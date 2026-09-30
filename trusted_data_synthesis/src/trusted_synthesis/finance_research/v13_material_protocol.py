"""Typed, one-shot missing supervision and whole-task mapping; no paid transport.

Original V12 process judgments and usable projections remain immutable. This module
only specifies new material measurements, and never grants training admission.
"""

from __future__ import annotations

import copy
import json

from . import v10_review_protocol as mapping_semantics
from . import v11_process_review as projection_semantics
from .contracts import digest
from .qwen_protocol import strict_json_decoder
from .v12_review_protocol import public_payload

MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
BATCH_ID = "finqa-v13-20260930-material-01"
WIRE = "v13_typed_material_completion.v1"
CAPS = (2048, 16384, 32768, 65536, 131072)
CONTEXT_CEILING = 1048576
CRITICAL = {"evidence_and_operations", "unwithdrawn_critical_contradictions"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def bound(value):
    return {**value, "id": digest(value)}


def policy_definition():
    return bound(
        dict(
            schema="v13_material_policy.v1",
            model=MODEL,
            wire_protocol=WIRE,
            fixed_original_packages=2468,
            fixed_tasks=744,
            retained_V12_projections=1797,
            missing_projection_calls=671,
            multipackage_mapping_calls=645,
            deterministic_singletons=99,
            total_new_calls=1316,
            calls_per_registered_job=1,
            retries=0,
            authority="retain usable original V12 A; new projection only for fixed missing list",
            process_judgments_unchanged=True,
            projection_does_not_filter_common_kernel=True,
            mapping_uses_full_originals_not_supervised_subset=True,
            singleton_chi=None,
            singleton_chi_status="not_required_for_weighting",
            singleton_is_not_ambiguous_multislot_fallback=True,
            empty_selectable_domain="offline reject, never empty enum or drop package",
            typed_AB_helper="CPU only; no registered dispatch",
            no_per_package_reason_minimum=True,
            no_JSON_repair=True,
            no_financial_rejudgment=True,
            semantic_truth_proved=False,
            output_caps=list(CAPS),
            capacity_is_estimate_not_guarantee=True,
            no_input_clipping=True,
            no_output_clipping=True,
            strict_tool_unsupported_size_constraints_used=False,
            production_admitted=False,
        )
    )


def _object(properties):
    return dict(
        type="object", properties=properties, required=list(properties), additionalProperties=False
    )


def _array(items):
    return dict(type="array", items=items)


def _enum(values, name):
    require(bool(values), "empty selectable domain: " + name)
    require(len(values) == len(set(values)), "duplicate selectable ID: " + name)
    return dict(type="string", enum=list(values))


def _tool(properties):
    return dict(
        type="function",
        function=dict(
            name="submit_material",
            strict=True,
            description="Return one original-bound material annotation object, no extra output.",
            parameters=_object(properties),
        ),
    )


def typed_domains(view):
    require(
        view.get("view_id")
        == "public_trajectory:" + digest({k: v for k, v in view.items() if k != "view_id"}),
        "original public view changed",
    )
    catalog = projection_semantics._catalog(view)
    # This lossless traversal also rejects omitted, duplicated and foreign public segments.
    public_payload(view, catalog, "material")
    documents = {d["segment_id"]: d for d in view["segments"]}
    evidence = [u["unit_id"] for u in catalog["units"] if u["end"] > u["start"]]
    reasons = [
        u["unit_id"]
        for u in catalog["units"]
        if u["kind"] == "public_content" and u["end"] > u["start"]
    ]
    events = {e["event_id"]: e for e in catalog["events"]}
    successful = []
    for action in catalog["actions"]:
        args = documents[action["arguments_segment_id"]]["text"]
        if args:
            evidence.append(action["action_id"])
        event = events.get(action["event_id"])
        if (
            args
            and event is not None
            and event["action_id"] == action["action_id"]
            and (event["name"] == action["name"] and event["is_error"] is False)
        ):
            successful.append(action["action_id"])
    for event in catalog["events"]:
        if documents[event["observation_segment_id"]]["text"]:
            evidence.append(event["event_id"])
    require(len(evidence) == len(set(evidence)), "public evidence ID collision")
    return dict(
        evidence_ids=evidence, reason_ids=reasons, successful_action_ids=successful, catalog=catalog
    )


def projection_tool(domains):
    reason = _enum(domains["reason_ids"], "R_nonempty_public_content")
    action = _enum(domains["successful_action_ids"], "Aok_actual_successful_actions")
    return _tool(
        dict(
            status=dict(type="string", enum=["complete", "unknown"]),
            positive_reason_ids=_array(reason),
            partial_positive_reason=_array(_object(dict(id=reason, quote=dict(type="string")))),
            positive_action_ids=_array(action),
        )
    )


def typed_ab_tool(view, role):
    """Prospective CPU/schema helper only. A/B has no V13 production job kind."""
    require(role in {"A", "B"}, "typed AB role required")
    domains = typed_domains(view)
    evidence = _enum(domains["evidence_ids"], "E_nonempty_evidence")
    checks = {}
    for name in projection_semantics.DIMENSIONS:
        statuses = ["supported", "critical_error", "unknown"]
        if name not in CRITICAL:
            statuses.append("not_applicable")
        checks[name] = _object(
            dict(
                status=dict(type="string", enum=statuses),
                summary=dict(type="string"),
                evidence_ids=_array(evidence),
                partial_evidence=_array(_object(dict(id=evidence, quote=dict(type="string")))),
            )
        )
    properties = dict(process=_object(checks))
    if role == "A":
        properties["supervision"] = projection_tool(domains)["function"]["parameters"]
    return _tool(properties)


def _mapping_domains(views, domains):
    references, observations, consequences = {}, [], []
    actions = []
    for index, (view, local) in enumerate(zip(views, domains, strict=True)):
        for unit in local["catalog"]["units"]:
            if unit["end"] <= unit["start"]:
                continue
            key = f"p{index}:" + unit["unit_id"]
            references[key] = dict(slot_id=view["slot_id"], id=unit["unit_id"])
            if unit["kind"] == "tool_observation":
                observations.append(key)
            if unit["kind"] in {"public_content", "action_arguments"}:
                consequences.append(key)
        actions.extend(a["action_id"] for a in local["catalog"]["actions"])
    return dict(
        references=references,
        evidence_ids=list(references),
        action_ids=actions,
        observation_ids=observations,
        consequence_ids=consequences,
    )


def mapping_tool(views, domains):
    slots = _enum([v["slot_id"] for v in views], "mapping_slots")
    ev = _enum(domains["evidence_ids"], "mapping_nonempty_evidence")
    partial = _object(dict(id=ev, quote=dict(type="string")))
    intervention = _object(
        dict(
            slot_id=slots,
            kind=dict(type="string", enum=["verification", "revision"]),
            action_id=_enum(domains["action_ids"], "mapping_actual_actions"),
            observation_id=_enum(domains["observation_ids"], "mapping_nonempty_observations"),
            consequence_id=_enum(domains["consequence_ids"], "mapping_later_model_consequences"),
            partial_consequence_quote=dict(type="string"),
            effect=dict(type="string"),
        )
    )
    return _tool(
        dict(
            mapping_status=dict(type="string", enum=["complete", "unknown"]),
            states=_array(
                _object(
                    dict(
                        state_id=dict(type="string"),
                        slot_ids=_array(slots),
                        semantic_summary=dict(type="string"),
                        evidence_ids=_array(ev),
                        partial_evidence=_array(partial),
                        chi=dict(type="integer", enum=[0, 1]),
                        chi_reason=dict(type="string"),
                        interventions=_array(intervention),
                    )
                )
            ),
            ambiguities=_array(
                _object(
                    dict(
                        slot_ids=_array(slots),
                        description=dict(type="string"),
                        evidence_ids=_array(ev),
                        partial_evidence=_array(partial),
                    )
                )
            ),
        )
    )


PROJECTION_RUBRIC = """Complete only the missing supervision annotation for this fixed
original public trajectory. Its prior A/B process qualification is unchanged; do not
re-review it or approve every statement merely because its final process passed.
Return one flat submit_material object: status, positive_reason_ids,
partial_positive_reason, positive_action_ids. Use status complete or unknown.
Choose positive_reason_ids ONLY from R (nonempty original public content), never
source, tool observation, or action-argument units. Choose positive_action_ids ONLY
from Aok (actually successful actions); success permits selection but does not
automatically approve learning from it. Host includes full original action arguments.
All original source, empty units, observations, earlier errors, withdrawals and
chronology remain visible. Unapproved content stays zero-target context. No minimum
positive reason length or number of approved actions is required. Do not overlap
whole and partial selections. Partial quotes must be nonempty exact contiguous
substrings unique in their original segment and contained within the selected unit.
Preserve semantic qualifiers. No normalization, fuzzy matches, offsets, parameter
copying, repaired JSON, or invented ID. If uncertain return unknown. No retry.
"""

MAPPING_RUBRIC = """Partition ALL supplied original packages for ONE task into actual
semantic behavior states in one submit_material response. See full original histories,
not approved supervision excerpts, previous state labels, private gold, or review text.
Use evidence selection, derivation dependencies, observation interpretation, and
consequential verification/revision; not wording, IDs, length, tool count/order,
endpoint/movement templates or direct/execute/error patterns. No pairwise enumeration
or proposition graph. state_id is just your local label. A complete partition assigns
every supplied slot exactly once. If ambiguous retain mapping_status unknown and
describe/locate the uncertainty; do not drop it or fabricate singleton states.
Evidence IDs are task-local p#:u# original nonempty units. Host derives exact original
coordinates. Partial evidence uses nonempty exact unique quote, never offsets.
chi=1 requires substantive actual verification/revision affecting later judgment or
action. For EACH member of a chi=1 state include a real intervention: actual action_id,
the corresponding original observation_id, a later model consequence_id and effect.
partial_consequence_quote="" selects the whole consequence unit; otherwise provide
one nonempty exact unique substring. Observations cannot masquerade as later model
behavior. Failed tools, narration of checking, changed arguments or ordinary execution
alone do not establish consequential revision. For chi=0 interventions must be empty.
Each state must have coherent chi; uncertainty remains unknown. Do not infer financial
truth from a bound locator or tool success. Retain every original and its process label.
"""


def _capacity(purpose, views, domains, mapping_domains=None):
    if purpose == "projection":
        local = domains[0]
        units = {u["unit_id"]: u for u in local["catalog"]["units"]}
        scenario = dict(
            status="complete",
            positive_reason_ids=local["reason_ids"],
            partial_positive_reason=[
                dict(id=i, quote=units[i]["text"]) for i in local["reason_ids"]
            ],
            positive_action_ids=local["successful_action_ids"],
        )
    else:
        states = []
        for index, (view, local) in enumerate(zip(views, domains, strict=True)):
            refs = [
                r
                for r, info in mapping_domains["references"].items()
                if info["slot_id"] == view["slot_id"]
            ]
            longest = sorted(
                (u for u in local["catalog"]["units"] if u["text"]),
                key=lambda u: len(canonical(u["text"])),
                reverse=True,
            )[:4]
            observations = [r for r in mapping_domains["observation_ids"] if r in refs]
            consequences = [r for r in mapping_domains["consequence_ids"] if r in refs]
            # Planning allowance only, never an actual claimed intervention or validator maximum.
            interventions = [
                dict(
                    slot_id=view["slot_id"],
                    kind="verification",
                    action_id=a["action_id"],
                    observation_id=observations[0] if observations else "",
                    consequence_id=consequences[0] if consequences else "",
                    partial_consequence_quote="",
                    effect="x" * 512,
                )
                for a in local["catalog"]["actions"]
            ]
            states.append(
                dict(
                    state_id=f"state-{index}",
                    slot_ids=[view["slot_id"]],
                    semantic_summary="x" * 1024,
                    evidence_ids=refs,
                    partial_evidence=[
                        dict(id=f"p{index}:" + u["unit_id"], quote=u["text"]) for u in longest
                    ],
                    chi=1,
                    chi_reason="x" * 1024,
                    interventions=interventions,
                )
            )
        scenario = dict(mapping_status="complete", states=states, ambiguities=[])
    size = len(canonical(scenario)) + 1024
    estimate = (5 * size + 3) // 4
    cap = next((n for n in CAPS if n >= estimate), None)
    require(cap is not None, "material output estimate exceeds allowed maximum; no clipping")
    return dict(
        schema="v13_serialized_response_capacity.v1",
        purpose=purpose,
        scenario_sha256=digest(scenario),
        scenario_utf8_bytes=size - 1024,
        tool_envelope_utf8_bytes=1024,
        safety_multiplier="5/4",
        estimated_output_requirement=estimate,
        max_output_tokens=cap,
        exact_token_forecast=False,
        hard_output_size_guarantee=False,
        planning_scenario_is_not_annotation=True,
        new_semantic_size_limits=False,
        input_or_output_clipping=False,
    )


def _prepare(views, purpose, protocol_id, source_bindings):
    require(purpose in {"projection", "mapping"}, "no A/B dispatch in V13")
    require(
        bool(protocol_id) and isinstance(source_bindings, dict) and source_bindings,
        "protocol and original source bindings required",
    )
    views = copy.deepcopy(views)
    require(
        len(views) == 1 if purpose == "projection" else 2 <= len(views) <= 8,
        "one projection or 2..8 original same-task mapping packages required",
    )
    task_ids = {v["task_id"] for v in views}
    slots = [v["slot_id"] for v in views]
    require(len(task_ids) == 1 and len(slots) == len(set(slots)), "same unique task slots required")
    if purpose == "mapping":
        require(
            set(source_bindings.get("task_slot_ids", [])) == set(slots),
            "complete registered task kernel required, no subset mapping",
        )
    domains = [typed_domains(v) for v in views]
    md = _mapping_domains(views, domains) if purpose == "mapping" else None
    tool = projection_tool(domains[0]) if purpose == "projection" else mapping_tool(views, md)
    packages = []
    for index, (view, local) in enumerate(zip(views, domains, strict=True)):
        payload = public_payload(view, local["catalog"], purpose)
        payload.update(wire_protocol=WIRE, slot_id=view["slot_id"], package_alias=f"p{index}")
        packages.append(payload)
    selectable = (
        {k: domains[0][k] for k in ("evidence_ids", "reason_ids", "successful_action_ids")}
        if purpose == "projection"
        else md
    )
    messages = [
        dict(
            role="system", content=PROJECTION_RUBRIC if purpose == "projection" else MAPPING_RUBRIC
        ),
        dict(
            role="user",
            content=canonical(
                dict(
                    wire_protocol=WIRE,
                    purpose=purpose,
                    task_id=views[0]["task_id"],
                    packages=packages,
                    selectable_domains=selectable,
                )
            ).decode(),
        ),
    ]
    capacity = _capacity(purpose, views, domains, md)
    coordinate = dict(
        protocol_id=protocol_id,
        **({"slot_id": slots[0]} if purpose == "projection" else {"task_id": views[0]["task_id"]}),
    )
    request = bound(
        dict(
            schema="v13_material_request.v1",
            wire_protocol=WIRE,
            batch_id=BATCH_ID,
            protocol_id=protocol_id,
            policy_id=policy_definition()["id"],
            model=MODEL,
            purpose=purpose,
            role=purpose,
            task_id=views[0]["task_id"],
            slot_id=slots[0] if purpose == "projection" else None,
            slot_ids=slots,
            episode_id="v13" + purpose + ":" + digest(coordinate),
            views=views,
            domains=domains,
            mapping_domains=md,
            source_bindings=copy.deepcopy(source_bindings),
            messages=messages,
            strict_tool=tool,
            capacity=capacity,
            max_output_tokens=capacity["max_output_tokens"],
            original_public_text_preserved=True,
            private_reference_or_old_annotation_in_messages=False,
        )
    )
    require(
        len(canonical(_body(request))) + request["max_output_tokens"] < CONTEXT_CEILING,
        "full input plus output cap exceeds conservative context envelope",
    )
    return request


def prepare_projection(view, *, protocol_id, source_bindings):
    return _prepare([view], "projection", protocol_id, source_bindings)


def prepare_mapping(views, *, protocol_id, source_bindings):
    return _prepare(views, "mapping", protocol_id, source_bindings)


def checked_request(request):
    require(request.get("model") == MODEL, "V13 model must be deepseek-flash")
    expected = _prepare(
        request["views"], request["purpose"], request["protocol_id"], request["source_bindings"]
    )
    require(request == expected, "V13 request public/body/source binding changed")
    return request


def _body(request):
    return dict(
        model=MODEL,
        messages=request["messages"],
        tools=[request["strict_tool"]],
        tool_choice=dict(type="function", function=dict(name="submit_material")),
        thinking=dict(type="disabled"),
        temperature=0,
        top_p=1,
        stream=False,
        max_tokens=request["max_output_tokens"],
    )


def request_body(request):
    checked_request(request)
    return _body(request)


def _validate_wire(value, schema, path="$"):
    kind = schema["type"]
    require(
        (kind == "object" and isinstance(value, dict))
        or (kind == "array" and isinstance(value, list))
        or (kind == "string" and isinstance(value, str))
        or (kind == "integer" and type(value) is int),
        path + ": wrong wire type",
    )
    if "enum" in schema:
        require(value in schema["enum"], path + ": outside typed enum")
    if kind == "object":
        require(set(value) == set(schema["properties"]), path + ": missing/extra wire field")
        for name, item in value.items():
            _validate_wire(item, schema["properties"][name], path + "." + name)
    elif kind == "array":
        for index, item in enumerate(value):
            _validate_wire(item, schema["items"], path + f"[{index}]")


def _decode(request, artifact):
    checked_request(request)
    raw = artifact["review_text"]
    parsed, errors = None, []
    if not isinstance(raw, str):
        errors.append("missing_material_argument_text")
    else:
        try:
            parsed = strict_json_decoder().decode(raw)
            _validate_wire(parsed, request["strict_tool"]["function"]["parameters"])
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    if artifact["finish_reason"] != "tool_calls" or artifact.get("review_format_error"):
        errors.append("original_annotation_envelope_incomplete:" + str(artifact["finish_reason"]))
    return raw, parsed, errors


def inspect_projection(request, artifact):
    require(request["purpose"] == "projection", "not a projection request")
    raw, parsed, errors = _decode(request, artifact)
    view, catalog = request["views"][0], request["domains"][0]["catalog"]
    derived, projection = None, None
    if not errors:
        try:
            require(
                all(p["quote"] for p in parsed["partial_positive_reason"]),
                "partial reason quote must be nonempty exact text",
            )
            derived = dict(
                status=parsed["status"],
                positive_content=[dict(id=i, quote=None) for i in parsed["positive_reason_ids"]]
                + copy.deepcopy(parsed["partial_positive_reason"]),
                positive_actions=copy.deepcopy(parsed["positive_action_ids"]),
            )
            projection = projection_semantics._projection(derived, view, catalog)
            if projection["error"]:
                errors.append(projection["error"])
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    usable = bool(not errors and projection and projection["usable"])
    raw_chars = sum(len(s["text"]) for s in view["segments"] if s["kind"] == "public_content")
    positive = (
        sum(s["end"] - s["start"] for s in projection["positive_content"]) if usable else None
    )
    return bound(
        dict(
            schema="v13_projection_inspection.v1",
            request_id=request["id"],
            protocol_id=request["protocol_id"],
            slot_id=view["slot_id"],
            task_id=view["task_id"],
            source_bindings=request["source_bindings"],
            raw_review=raw,
            raw_wire_annotation=parsed,
            deterministic_materialized_annotation=derived,
            projection=projection,
            usable=usable,
            errors=errors,
            reason_projection=dict(
                raw_public_characters=raw_chars,
                positive_public_characters=positive,
                all_public_reasoning_masked=(raw_chars > 0 and positive == 0) if usable else None,
            ),
            original_process_judgments_unchanged=True,
            JSON_repaired=False,
            actual_model_call_receipt_verified=False,
            production_admitted=False,
            semantic_truth_proved=False,
        )
    )


def _mapping_locator(request, ref_id, quote=None):
    reference = request["mapping_domains"]["references"][ref_id]
    index = next(i for i, v in enumerate(request["views"]) if v["slot_id"] == reference["slot_id"])
    located = projection_semantics._locate(
        dict(id=reference["id"], quote=quote),
        request["views"][index],
        request["domains"][index]["catalog"],
    )
    return dict(
        slot_id=reference["slot_id"],
        **{k: located[k] for k in ("segment_id", "start", "end", "quote")},
    )


def _mapping_evidence(request, value):
    result = [_mapping_locator(request, key) for key in value["evidence_ids"]]
    for part in value["partial_evidence"]:
        require(bool(part["quote"]), "partial mapping evidence must be nonempty")
        result.append(_mapping_locator(request, part["id"], part["quote"]))
    return result


def _materialize_mapping(request, parsed):
    result = dict(mapping_status=parsed["mapping_status"], states=[], ambiguities=[])
    for state in parsed["states"]:
        item = {
            k: copy.deepcopy(state[k])
            for k in ("state_id", "slot_ids", "semantic_summary", "chi", "chi_reason")
        }
        item["evidence"] = _mapping_evidence(request, state)
        item["interventions"] = []
        for event in state["interventions"]:
            observation = _mapping_locator(request, event["observation_id"])
            consequence = _mapping_locator(
                request, event["consequence_id"], event["partial_consequence_quote"] or None
            )
            require(
                observation["slot_id"] == consequence["slot_id"] == event["slot_id"],
                "intervention references must belong to same original slot",
            )
            item["interventions"].append(
                dict(
                    slot_id=event["slot_id"],
                    kind=event["kind"],
                    action_id=event["action_id"],
                    observation_segment_id=observation["segment_id"],
                    consequence={k: v for k, v in consequence.items() if k != "slot_id"},
                    effect=event["effect"],
                )
            )
        result["states"].append(item)
    for ambiguity in parsed["ambiguities"]:
        result["ambiguities"].append(
            dict(
                slot_ids=ambiguity["slot_ids"],
                description=ambiguity["description"],
                evidence=_mapping_evidence(request, ambiguity),
            )
        )
    return result


def inspect_mapping(request, artifact):
    require(request["purpose"] == "mapping", "not a mapping request")
    raw, parsed, errors = _decode(request, artifact)
    derived, result = None, None
    if not errors:
        try:
            derived = _materialize_mapping(request, parsed)
            result = mapping_semantics._inspect_mapping(
                canonical(derived).decode(),
                dict(packages=[dict(slot_id=v["slot_id"], trajectory=v) for v in request["views"]]),
            )
            if result["error"]:
                errors.append(result["error"])
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    complete = bool(not errors and result and result["mapping_status"] == "complete")
    states = result["parsed"]["states"] if result and result["parsed"] else []
    return bound(
        dict(
            schema="v13_mapping_inspection.v1",
            request_id=request["id"],
            protocol_id=request["protocol_id"],
            task_id=request["task_id"],
            slot_ids=request["slot_ids"],
            source_bindings=request["source_bindings"],
            raw_review=raw,
            raw_wire_annotation=parsed,
            deterministic_materialized_annotation=derived,
            errors=errors,
            annotation_status="annotation_succeeded" if not errors else "annotation_failed",
            mapping_status="complete" if complete else "unknown",
            states=states,
            state_by_slot={slot: s["state_id"] for s in states for slot in s["slot_ids"]}
            if complete
            else {},
            chi_by_state={s["state_id"]: s["chi"] for s in states} if complete else {},
            chi_status="semantically_annotated" if complete else "unknown",
            deterministic_singleton=False,
            mapping_admitted=complete,
            original_process_judgments_unchanged=True,
            no_ambiguous_package_dropped=True,
            JSON_repaired=False,
            actual_model_call_receipt_verified=False,
            production_admitted=False,
            semantic_truth_proved=False,
        )
    )


def inspect_paid_annotation(request, artifact):
    require(request["purpose"] in {"projection", "mapping"}, "no A/B dispatch in V13")
    return (inspect_projection if request["purpose"] == "projection" else inspect_mapping)(
        request, artifact
    )


def validate_inspection(inspection, request, artifact):
    require(
        inspection == inspect_paid_annotation(request, artifact),
        "inspection changed from raw/source",
    )
    return inspection


def singleton(view, *, protocol_id, source_bindings):
    typed_domains(view)
    require(
        source_bindings.get("task_slot_ids") == [view["slot_id"]],
        "deterministic singleton requires exactly one registered original task member",
    )
    state_id = "singleton:" + digest(dict(task_id=view["task_id"], slot_id=view["slot_id"]))
    return bound(
        dict(
            schema="v13_mapping_inspection.v1",
            request_id=None,
            protocol_id=protocol_id,
            task_id=view["task_id"],
            slot_ids=[view["slot_id"]],
            source_bindings=copy.deepcopy(source_bindings),
            view_id=view["view_id"],
            raw_review=None,
            raw_wire_annotation=None,
            deterministic_materialized_annotation=None,
            errors=[],
            annotation_status="not_required",
            mapping_status="complete",
            states=[
                dict(
                    state_id=state_id,
                    slot_ids=[view["slot_id"]],
                    chi=None,
                    chi_status="not_required_for_weighting",
                    partition_authority="one_element_support",
                )
            ],
            state_by_slot={view["slot_id"]: state_id},
            chi_by_state={state_id: None},
            chi_status="not_required_for_weighting",
            deterministic_singleton=True,
            r={state_id: 1},
            pi={state_id: 1},
            centered_gradient=0,
            novelty=0,
            mapping_admitted=True,
            original_process_judgments_unchanged=True,
            actual_model_calls=0,
            actual_model_call_receipt_verified=False,
            production_admitted=False,
            semantic_truth_proved=False,
        )
    )
