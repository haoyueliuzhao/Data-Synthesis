"""Fixed 54-task V15 mapping interpretation and one residual annotation only.

The already resolved 690 authorities, all original packages, supervision and
encoded rows are immutable inputs. No Student information or paid transport here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from pydantic import Field

from . import v14_material_protocol as previous
from .contracts import digest
from .qwen_protocol import strict_json_decoder

MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
BATCH_ID = "finqa-v15-20260930-prefix-completion-01"
WIRE = "v15_fixed_targeted_mapping.v1"
bound, require, canonical = previous.bound, previous.require, previous.canonical
legacy = previous.old.mapping_semantics


class OptionalSummaryState(legacy.SemanticState):
    semantic_summary: str | None = Field(default=None, min_length=1)


class OptionalSummaryMapping(legacy.MappingOutput):
    states: list[OptionalSummaryState]


def policy_definition():
    return bound(
        dict(
            schema="v15_targeted_mapping_policy.v1",
            model=MODEL,
            fixed_target_tasks=54,
            unchanged_prior_tasks=690,
            original_tasks=744,
            original_packages=2468,
            scope="only original fixed unresolved V14 mapping tasks; no A/B or supervision changes",
            missing_summary=dict(
                default=None,
                no_text_filled=True,
                requirement="explicit source-bound interpretation of existing classification basis",
                finite_eligibility=(
                    "one whole-task state, original chi=0, no interventions, every member evidenced"
                ),
                interpreter="Codex_source_interpretation",
                independent_financial_truth=False,
                new_model_or_chi_label=False,
                complete_contract_still_required=True,
            ),
            partial_quote=(
                "exact nonempty unchanged quote unique within the already selected original unit"
            ),
            no_fuzzy_matching=True,
            no_neighbor_unit_search=True,
            no_first_occurrence_selection=True,
            no_qualifier_removal=True,
            original_IDs_members_chi_and_text_unchanged=True,
            unproved_semantics_or_missing_key=(
                "residual one new predeclared annotation, not guessed"
            ),
            new_wire=(
                "short package/action/evidence IDs; "
                "one basis carries classification and chi rationale"
            ),
            summary_not_fabricated_from_basis=True,
            calls_per_residual=1,
            automatic_retries=0,
            Student_information_visible=False,
            training_or_mask_changes=False,
            production_admitted=False,
        )
    )


def _read(path, ref=None):
    return previous._read(path, ref)


def _write(path, value):
    return previous._write(path, value)


def _hashes():
    return {
        **previous._source_hashes(),
        "v15_mapping_protocol.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def register_basis_interpretation(candidates_path, output_root, *, approved_task_ids):
    """Call only after the declared interpreter has read the existing evidence."""
    candidates, source = _read(candidates_path)
    require(
        candidates["schema"] == "v15_existing_basis_review_candidates.v1"
        and candidates["authority_approved"] is False,
        "source reading candidates required",
    )
    selected = list(approved_task_ids)
    available = {r["task_id"]: r for r in candidates["candidates"]}
    require(
        len(selected) == len(set(selected)) and set(selected) <= set(available),
        "explicit unique reviewed tasks only",
    )
    approvals = []
    for task in selected:
        item = available[task]
        approvals.append(
            dict(
                task_id=task,
                candidate_id=item["id"],
                source_record_ref=item["source_record"],
                raw_review_sha256=item["raw_review_sha256"],
                basis_source_path=item["basis_source_path"],
                original_basis_text_sha256=hashlib.sha256(
                    item["original_chi_reason"].encode()
                ).hexdigest(),
                members=item["members"],
                approved_existing_basis=True,
            )
        )
    value = bound(
        dict(
            schema="v15_existing_basis_interpretation.v1",
            policy_id=policy_definition()["id"],
            candidates=source,
            approvals=approvals,
            actor="Codex_source_interpretation",
            interpretation=(
                "existing original rationale explicitly supplies whole-member "
                "common derivation and no consequential verification difference"
            ),
            not_independent_financial_truth=True,
            not_new_model_response=True,
            no_new_chi_label=True,
            summary_remains_not_supplied=True,
            complete_remaining_contract_required=True,
            Student_results_read=False,
            actual_model_calls=0,
            production_admitted=False,
        )
    )
    _write(Path(output_root) / "mapping_basis_interpretation", value)
    return value


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
        require(
            set(schema["required"]) <= set(value) <= set(schema["properties"]),
            path + ": missing/extra wire field",
        )
        for key, item in value.items():
            _validate_wire(item, schema["properties"][key], path + "." + key)
    elif kind == "array":
        for index, item in enumerate(value):
            _validate_wire(item, schema["items"], path + f"[{index}]")


def _unit_location(request, key, quote, receipts):
    target = request["mapping_domains"]["references"][key]
    index = next(i for i, v in enumerate(request["views"]) if v["slot_id"] == target["slot_id"])
    unit = next(
        u for u in request["domains"][index]["catalog"]["units"] if u["unit_id"] == target["id"]
    )
    text, left, right = unit["text"], unit["start"], unit["end"]
    document = next(
        d for d in request["views"][index]["segments"] if d["segment_id"] == unit["segment_id"]
    )
    require(
        document["text"][left:right] == text and left < right,
        "original nonempty unit binding changed",
    )
    if quote is not None:
        require(
            isinstance(quote, str) and quote,
            "partial quote must remain nonempty exact original text",
        )
        positions, cursor = [], text.find(quote)
        while cursor >= 0:
            positions.append(cursor)
            cursor = text.find(quote, cursor + 1)
        require(
            len(positions) == 1,
            "partial quote must occur exactly once inside selected original unit",
        )
        left += positions[0]
        right = left + len(quote)
    else:
        quote = text
    require(document["text"][left:right] == quote, "no text normalization or span enlargement")
    receipts.append(
        dict(
            id=key,
            slot_id=target["slot_id"],
            original_unit_id=unit["unit_id"],
            original_segment_id=unit["segment_id"],
            unit_start=unit["start"],
            unit_end=unit["end"],
            start=left,
            end=right,
            exact_quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),
            rule="original_selected_unit_unique_exact",
        )
    )
    return dict(
        slot_id=target["slot_id"], segment_id=unit["segment_id"], start=left, end=right, quote=quote
    )


def _evidence(request, state, receipts):
    return [_unit_location(request, key, None, receipts) for key in state["evidence_ids"]] + [
        _unit_location(request, p["id"], p["quote"], receipts) for p in state["partial_evidence"]
    ]


def _materialize(request, expanded, receipts):
    result = dict(mapping_status=expanded["mapping_status"], states=[], ambiguities=[])
    for state in expanded["states"]:
        item = {
            k: copy.deepcopy(state[k])
            for k in ("state_id", "slot_ids", "semantic_summary", "chi", "chi_reason")
        }
        item["evidence"] = _evidence(request, state, receipts)
        item["interventions"] = []
        for event in state["interventions"]:
            observation = _unit_location(request, event["observation_id"], None, receipts)
            consequence = _unit_location(
                request,
                event["consequence_id"],
                event["partial_consequence_quote"] or None,
                receipts,
            )
            require(
                observation["slot_id"] == consequence["slot_id"] == event["slot_id"],
                "intervention references belong to different original packages",
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
    for note in expanded["ambiguities"]:
        result["ambiguities"].append(
            dict(
                slot_ids=note["slot_ids"],
                description=note["description"],
                evidence=_evidence(request, note, receipts),
            )
        )
    return result


def _semantic_contract(materialized, request):
    """Same finite member/evidence/chi contract; absent summary is explicit None."""
    value = OptionalSummaryMapping.model_validate(materialized)
    packages = {v["slot_id"]: v for v in request["views"]}
    documents = {sid: {d["segment_id"]: d for d in v["segments"]} for sid, v in packages.items()}
    seen, state_ids = [], set()
    for state in value.states:
        require(state.state_id not in state_ids, "duplicate state locator")
        state_ids.add(state.state_id)
        require(
            len(state.slot_ids) == len(set(state.slot_ids))
            and set(state.slot_ids) <= set(packages),
            "unknown or duplicate state member",
        )
        seen.extend(state.slot_ids)
        for ev in state.evidence:
            require(ev.slot_id in state.slot_ids, "state evidence must belong to its members")
            legacy._located(ev.model_dump(), documents[ev.slot_id])
        demonstrated = set()
        for event in state.interventions:
            require(event.slot_id in state.slot_ids, "chi evidence belongs to another state")
            view = packages[event.slot_id]
            actions = {
                a["action_id"]: (a, t["turn_index"]) for t in view["turns"] for a in t["actions"]
            }
            require(event.action_id in actions, "chi action not executed in original package")
            action, turn = actions[event.action_id]
            observation = next(
                (e for e in view["events"] if e["event_id"] == action["event_id"]), None
            )
            require(
                observation is not None
                and observation["observation_segment_id"] == event.observation_segment_id,
                "chi requires original action/observation pair",
            )
            consequence = legacy._located(event.consequence.model_dump(), documents[event.slot_id])
            require(
                consequence["kind"] in {"public_content", "action_arguments"}
                and consequence["turn_index"] > turn,
                "chi consequence must be later original model behavior",
            )
            demonstrated.add(event.slot_id)
        require(
            (state.chi == 1 and demonstrated == set(state.slot_ids))
            or (state.chi == 0 and not state.interventions),
            "chi cannot be inferred from one exemplar or tool count",
        )
    require(len(seen) == len(set(seen)), "one package cannot belong to two states")
    for note in value.ambiguities:
        require(set(note.slot_ids) <= set(packages), "ambiguity refers to foreign package")
        for ev in note.evidence:
            require(ev.slot_id in note.slot_ids, "ambiguity evidence mismatch")
            legacy._located(ev.model_dump(), documents[ev.slot_id])
    if value.mapping_status == "complete":
        require(
            set(seen) == set(packages) and not value.ambiguities,
            "complete mapping requires all packages and no ambiguity",
        )
    else:
        require(value.ambiguities, "unknown mapping must retain stated ambiguity")
    return value.model_dump(mode="json")


def _approved_missing_basis(record, parsed, approvals, source_ref):
    missing = [i for i, s in enumerate(parsed["states"]) if "semantic_summary" not in s]
    if not missing:
        return []
    require(
        missing == [0] and len(parsed["states"]) == 1,
        "missing summary has no approved whole-task basis",
    )
    state, req = parsed["states"][0], record["request"]
    approval = approvals.get(record["task_id"])
    require(
        approval is not None and approval["approved_existing_basis"] is True,
        "missing summary needs explicit original-basis interpretation",
    )
    require(
        state["chi"] == 0
        and not state["interventions"]
        and len(state["members"]) == len(set(state["members"]))
        and set(state["members"]) == set(req["aliases"]["packages"]),
        "only originally stated single whole-task chi0 equivalence can use this interpretation",
    )
    require(
        approval["source_record_ref"] == source_ref
        and approval["raw_review_sha256"]
        == hashlib.sha256(record["artifact"]["review_text"].encode()).hexdigest()
        and approval["basis_source_path"] == "raw_wire_annotation.states[0].chi_reason"
        and approval["original_basis_text_sha256"]
        == hashlib.sha256(state["chi_reason"].encode()).hexdigest()
        and approval["members"] == state["members"],
        "basis interpretation source changed",
    )
    evidence_ids = state["evidence_ids"] + [p["id"] for p in state["partial_evidence"]]
    evidenced = {req["mapping_domains"]["references"][e]["slot_id"] for e in evidence_ids}
    require(
        evidenced == set(req["slot_ids"]),
        "existing class basis must have every original member evidenced",
    )
    return [
        dict(
            state_index=0,
            source_path=approval["basis_source_path"],
            text=state["chi_reason"],
            candidate_id=approval["candidate_id"],
            summary_originally_not_supplied=True,
            bounded_existing_statement_interpretation=True,
        )
    ]


def derive_mapping(record, source_ref, *, approvals=None, approval_ref=None):
    require(
        record.get("schema") == "v14_paid_material_annotation.v1"
        and record["actual_model_call_receipt_verified"] is True
        and record["purpose"] == "mapping"
        and record["id"] == source_ref["id"]
        and record["id"] == digest({k: v for k, v in record.items() if k != "id"}),
        "actual original V14 mapping required",
    )
    req, art = record["request"], record["artifact"]
    parsed, expanded, materialized, validated, errors, receipts, bases = (
        None,
        None,
        None,
        None,
        [],
        [],
        [],
    )
    raw = art["review_text"]
    try:
        require(
            art["finish_reason"] == "tool_calls" and not art["review_format_error"],
            "original envelope incomplete",
        )
        parsed = strict_json_decoder().decode(raw)
        schema = copy.deepcopy(req["strict_tool"]["function"]["parameters"])
        schema["properties"]["states"]["items"]["required"].remove("semantic_summary")
        _validate_wire(parsed, schema)
        bases = _approved_missing_basis(record, parsed, approvals or {}, source_ref)
        body = copy.deepcopy(parsed)
        for state in body["states"]:
            state.setdefault("semantic_summary", None)
        expanded = previous._expand_mapping(req, body)
        materialized = _materialize(req, expanded, receipts)
        validated = _semantic_contract(materialized, req)
    except (ValueError, TypeError, KeyError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    inspection = _inspection(
        req,
        raw,
        parsed,
        expanded,
        materialized,
        validated,
        errors,
        receipts,
        bases,
        schema="v15_derived_mapping_inspection.v1",
    )
    return bound(
        dict(
            schema="v15_derived_mapping.v1",
            policy_id=policy_definition()["id"],
            task_id=record["task_id"],
            source_record_ref=source_ref,
            source_request_id=req["id"],
            source_inspection_id=record["inspection"]["id"],
            basis_interpretation_ref=approval_ref,
            raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest()
            if isinstance(raw, str)
            else None,
            original_failure_labels=record["inspection"]["errors"],
            inspection=inspection,
            usable=inspection["mapping_admitted"],
            original_summary_not_filled=True,
            original_members_and_chi_not_changed=True,
            supervision_and_encodings_changed=False,
            actual_model_calls=0,
            Student_information_read=False,
            production_admitted=False,
        )
    )


def _inspection(
    req, raw, parsed, expanded, materialized, validated, errors, receipts, bases, *, schema
):
    complete = not errors and validated is not None and validated["mapping_status"] == "complete"
    states = validated["states"] if validated else []
    return bound(
        dict(
            schema=schema,
            request_id=req["id"],
            protocol_id=req["protocol_id"],
            task_id=req["task_id"],
            slot_ids=req["slot_ids"],
            raw_review=raw,
            raw_wire_annotation=parsed,
            deterministic_expanded_wire=expanded,
            deterministic_materialized_annotation=materialized,
            states=states,
            mapping_status="complete" if complete else "unknown",
            mapping_admitted=complete,
            annotation_status="annotation_succeeded" if not errors else "annotation_failed",
            state_by_slot={s: z["state_id"] for z in states for s in z["slot_ids"]}
            if complete
            else {},
            chi_by_state={z["state_id"]: z["chi"] for z in states} if complete else {},
            chi_status="semantically_annotated" if complete else "unknown",
            deterministic_singleton=False,
            classification_basis_sources=bases,
            original_unit_resolution_receipts=receipts,
            errors=errors,
            JSON_repaired=False,
            semantic_truth_proved=False,
            actual_model_call_receipt_verified=False,
            production_admitted=False,
        )
    )


def review_existing(source_root, output_root, *, basis_approval_ref=None):
    source, output = Path(source_root).resolve(), Path(output_root).resolve() / "mapping_review"
    require(not (output / "summary/record.json").exists(), "review scope already frozen")
    hashes = _hashes()
    seal, seal_ref = _read(source / "completion_seal/record.json")
    plan, plan_ref = _read(source / "registration/record.json")
    representation, representation_ref = _read(
        seal["representation_review"]["path"], seal["representation_review"]
    )
    require(
        seal["actual_returns"] == seal["expected_calls"] == 309
        and seal["network_unknowns"] == 0
        and seal["mapping_complete_calls"] == 254
        and seal["failures"]["mapping"]["annotation_unusable"] == 54,
        "exact completed V14 population required",
    )
    approvals = {}
    if basis_approval_ref is not None:
        approval, _ = _read(basis_approval_ref["path"], basis_approval_ref)
        require(
            approval["schema"] == "v15_existing_basis_interpretation.v1"
            and approval["policy_id"] == policy_definition()["id"]
            and approval["actor"] == "Codex_source_interpretation"
            and approval["Student_results_read"] is False,
            "pre-Student bounded source interpretation required",
        )
        approvals = {r["task_id"]: r for r in approval["approvals"]}
        require(len(approvals) == len(approval["approvals"]), "duplicate basis interpretation")
    inherited = copy.deepcopy(representation["mapping_authority_refs"])
    inherited += [
        dict(task_id=r["task_id"], authority_kind="V13_deterministic_singleton", record=r["record"])
        for r in representation["inherited_singleton_refs"]
    ]
    pending, results = [], []
    for terminal_ref in seal["terminals"]:
        terminal, _ = _read(terminal_ref["path"], terminal_ref)
        record, ref = _read(terminal["record"]["path"], terminal["record"])
        if record["purpose"] != "mapping":
            continue
        if record["inspection"]["mapping_admitted"]:
            inherited.append(
                dict(task_id=record["task_id"], authority_kind="V14_completion_only", record=ref)
            )
        else:
            pending.append(record["task_id"])
            results.append(
                derive_mapping(record, ref, approvals=approvals, approval_ref=basis_approval_ref)
            )
    require(
        len(pending) == len(set(pending)) == 54
        and len(inherited) == 690
        and len({r["task_id"] for r in inherited}) == 690
        and not (set(pending) & {r["task_id"] for r in inherited}),
        "unchanged 690 and fixed 54 task support required",
    )
    for authority in inherited:
        _read(authority["record"]["path"], authority["record"])
    all_refs, accepted = [], []
    for result in results:
        ref = _write(output / "tasks" / digest(result["task_id"]), result)
        entry = dict(task_id=result["task_id"], authority_kind="V15_derived_mapping", record=ref)
        all_refs.append(entry)
        if result["usable"]:
            accepted.append(entry)
    recovered = {r["task_id"] for r in accepted}
    require(hashes == _hashes(), "mapping interpretation code changed during review")
    summary = bound(
        dict(
            schema="v15_mapping_review.v1",
            policy=policy_definition(),
            source_v14_plan=plan_ref,
            source_v14_seal=seal_ref,
            source_v14_representation_review=representation_ref,
            basis_interpretation_ref=basis_approval_ref,
            source_protocol_hashes=hashes,
            fixed_task_ids=pending,
            inherited_mapping_authority_refs=inherited,
            derived_mapping_authority_refs=accepted,
            all_mapping_review_refs=all_refs,
            residual_mapping_task_ids=[t for t in pending if t not in recovered],
            reviewed_task_count=54,
            recovered_mapping_count=len(accepted),
            old_690_partition_evidence_chi_unchanged=True,
            unchanged_by_exact_source_references=True,
            no_supervision_or_encoding_change=True,
            Student_information_read=False,
            new_once_scope_frozen_before_Student=True,
            actual_model_calls=0,
            production_admitted=False,
        )
    )
    _write(output / "summary", summary)
    return summary


RUBRIC = """Complete one semantic mapping for the fixed complete original task.
Return exactly mapping_status, states, ambiguity_notes in one submit_material object.
Use short package p# and original evidence/action aliases. Membership appears only
once in states[].members; every package exactly once when complete. Do not make a
state for steps of a package, drop difficult members, or create states from wording,
length, tool counts, or ordinary execute/submit differences.
Each state has ONE basis string, not semantic_summary plus chi_reason. Its basis must
state both why these members share a semantic state/how distinct states differ, and
why chi is 0 or 1. This explanation must refer to original evidence/derivation,
observation interpretation, or truly consequential verification/revision, not just
identical final answers. Host will retain basis as its own original field, never
pretend it was an omitted old summary. No other side or previous annotation is shown.
Prefer WHOLE evidence IDs; partial_evidence is only for necessary exact subspans.
Every partial quote must be nonempty, unchanged, uniquely present WITHIN its selected
original unit. Never search adjacent units, fix spelling/numbers or trim qualifiers.
For chi=1 each member needs a real action, its actual corresponding observation,
and a later model consequence with substantive effect. Ordinary execution, repeating
a result or saying checked is not sufficient. chi=0 has no interventions. If the
partition or chi cannot be determined, return unknown and explain in ambiguity_notes;
do not fabricate a resolution. Do not output state IDs; Host assigns them canonically.
"""


def _capacity(base):
    states = []
    for index, local in enumerate(base["domains"]):
        prefix = f"p{index}:"
        refs = [r for r in base["mapping_domains"]["evidence_ids"] if r.startswith(prefix)]
        longest = sorted(
            (u for u in local["catalog"]["units"] if u["text"]),
            key=lambda u: len(canonical(u["text"])),
            reverse=True,
        )[:4]
        observations = [
            r for r in base["mapping_domains"]["observation_ids"] if r.startswith(prefix)
        ]
        consequences = [
            r for r in base["mapping_domains"]["consequence_ids"] if r.startswith(prefix)
        ]
        states.append(
            dict(
                members=[f"p{index}"],
                basis="x" * 2048,
                evidence_ids=refs,
                partial_evidence=[dict(id=prefix + u["unit_id"], quote=u["text"]) for u in longest],
                chi=1,
                interventions=[
                    dict(
                        kind="verification",
                        action=a,
                        observation=observations[0] if observations else "",
                        consequence=consequences[0] if consequences else "",
                        partial_consequence_quote="",
                        effect="x" * 512,
                    )
                    for a in base["aliases"]["actions"]
                    if a.startswith(prefix)
                ],
            )
        )
    scenario = dict(mapping_status="complete", states=states, ambiguity_notes=[])
    size = len(canonical(scenario)) + 1024
    estimate = (5 * size + 3) // 4
    cap = next((n for n in previous.old.CAPS if n >= estimate), None)
    require(cap is not None, "actual response plan exceeds allowed cap; never clip inputs")
    return dict(
        schema="v15_serialized_mapping_capacity.v1",
        scenario_sha256=digest(scenario),
        scenario_utf8_bytes=size - 1024,
        tool_envelope_utf8_bytes=1024,
        safety_multiplier="5/4",
        estimated_output_requirement=estimate,
        max_output_tokens=cap,
        exact_token_forecast=False,
        hard_output_size_guarantee=False,
        new_semantic_size_limits=False,
    )


def prepare_mapping(views, *, protocol_id, source_bindings):
    base = previous.prepare_mapping(views, protocol_id=protocol_id, source_bindings=source_bindings)
    tool = copy.deepcopy(base["strict_tool"])
    state = tool["function"]["parameters"]["properties"]["states"]["items"]
    for key in ("semantic_summary", "chi_reason"):
        del state["properties"][key]
    state["properties"]["basis"] = dict(type="string")
    state["required"] = list(state["properties"])
    payload = json.loads(base["messages"][1]["content"])
    payload["wire_protocol"] = WIRE
    for package in payload["packages"]:
        package["wire_protocol"] = WIRE
    cap = _capacity(base)
    request = {k: v for k, v in base.items() if k != "id"}
    request.update(
        schema="v15_mapping_request.v1",
        batch_id=BATCH_ID,
        wire_protocol=WIRE,
        policy_id=policy_definition()["id"],
        episode_id="v15" + base["episode_id"][3:],
        messages=[
            dict(role="system", content=RUBRIC),
            dict(role="user", content=canonical(payload).decode()),
        ],
        strict_tool=tool,
        capacity=cap,
        max_output_tokens=cap["max_output_tokens"],
    )
    request = bound(request)
    require(
        len(canonical(previous._body(request))) + request["max_output_tokens"]
        < previous.old.CONTEXT_CEILING,
        "complete public input plus output cap exceeds frozen envelope",
    )
    return request


def checked_request(request):
    require(
        request.get("model") == MODEL
        and request.get("purpose") == request.get("role") == "mapping",
        "V15 only fixed deepseek-flash mapping jobs",
    )
    require(
        request
        == prepare_mapping(
            request["views"],
            protocol_id=request["protocol_id"],
            source_bindings=request["source_bindings"],
        ),
        "fixed V15 source/body identity changed",
    )
    return request


def request_body(request):
    checked_request(request)
    return previous._body(request)


def inspect_reply(request, artifact):
    checked_request(request)
    raw = artifact["review_text"]
    parsed, expanded, materialized, validated, errors, receipts, bases = (
        None,
        None,
        None,
        None,
        [],
        [],
        [],
    )
    try:
        require(
            artifact["finish_reason"] == "tool_calls" and not artifact.get("review_format_error"),
            "original annotation envelope incomplete",
        )
        require(isinstance(raw, str), "missing mapping argument text")
        parsed = strict_json_decoder().decode(raw)
        _validate_wire(parsed, request["strict_tool"]["function"]["parameters"])
        translated = copy.deepcopy(parsed)
        for index, state in enumerate(translated["states"]):
            basis = state.pop("basis")
            require(bool(basis.strip()), "classification and chi basis cannot be empty")
            state.update(semantic_summary=None, chi_reason=basis)
            bases.append(
                dict(
                    raw_state_index=index,
                    source_path=f"raw_wire_annotation.states[{index}].basis",
                    text=basis,
                    actual_new_model_field=True,
                    not_an_original_semantic_summary=True,
                )
            )
        expanded = previous._expand_mapping(request, translated)
        materialized = _materialize(request, expanded, receipts)
        validated = _semantic_contract(materialized, request)
    except (ValueError, TypeError, KeyError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    return _inspection(
        request,
        raw,
        parsed,
        expanded,
        materialized,
        validated,
        errors,
        receipts,
        bases,
        schema="v15_mapping_inspection.v1",
    )


inspect_paid_annotation = inspect_reply


def validate_inspection(inspection, request, artifact):
    require(
        inspection == inspect_reply(request, artifact),
        "saved new interpretation differs from actual reply",
    )
    return inspection
