"""Append-only V14 interpretation and compact residual annotations; never transport.

Mechanical redundancy is deliberately narrow. Unproved natural-language extras
remain pending; no favorable label selection, JSON repair or character-span merging.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from . import v13_material_protocol as old
from .contracts import digest
from .qwen_protocol import strict_json_decoder
from .v6_collection import persist

MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
BATCH_ID = "finqa-v14-20260930-representation-01"
WIRE = "v14_compact_residual_material.v1"
TOKEN_SELECTION = "union_of_individually_bounded_original_spans"
CORE_FIELDS = ("mapping_status", "states", "ambiguities")
bound, require, canonical = old.bound, old.require, old.canonical


def policy_definition():
    return bound(
        dict(
            schema="v14_representation_policy.v1",
            model=MODEL,
            source="fixed entire V13 candidate population, all 633 returned mappings uniformly",
            original_successes_require_exact_states_evidence_chi=True,
            mapping_extras=dict(
                slot_ids="exact full unique original task member set only",
                semantic_summary="empty or exact already-present core state summary only",
                partial_evidence=(
                    "empty or each exact object already in core state partial evidence"
                ),
                all_other_or_unproved_content="pending; never silently stripped",
            ),
            auxiliary_original_preserved=True,
            auxiliary_never_fills_core=True,
            no_new_human_or_model_semantic_interpretation=True,
            strict_original_JSON_required=True,
            duplicate_keys_rejected=True,
            JSON_repair=False,
            projection=(
                "same-authority original positive spans individually retained; Boolean token union"
            ),
            token_selection=TOKEN_SELECTION,
            illegal_action_ID_not_guessed=True,
            original_successes_remain_authoritative=True,
            residual_once_authority_fixed_before_returns=True,
            original_network_unknown_and_reservation_retained=True,
            new_mapping_membership_expressed_once=True,
            state_IDs_generated_by_host=True,
            state_identity_not_text_hash_or_tool_count=True,
            output_caps=list(old.CAPS),
            output_capacity_is_estimate=True,
            retries=0,
            no_original_input_clipping=True,
            production_admitted=False,
        )
    )


def _checked_paid(record, source_ref, purpose):
    require(
        record.get("id") == digest({k: v for k, v in record.items() if k != "id"}),
        "original paid record content identity changed",
    )
    require(
        record.get("schema") == "v13_paid_material_annotation.v1"
        and record.get("actual_model_call_receipt_verified") is True
        and record["purpose"] == purpose
        and source_ref["id"] == record["id"],
        "this actual original V13 material return required",
    )


def _semantic_fields(inspection):
    return {k: inspection[k] for k in ("states", "state_by_slot", "chi_by_state")}


def _core_mapping(request, core):
    old._validate_wire(core, request["strict_tool"]["function"]["parameters"])
    derived = old._materialize_mapping(request, core)
    result = old.mapping_semantics._inspect_mapping(
        canonical(derived).decode(),
        dict(packages=[dict(slot_id=v["slot_id"], trajectory=v) for v in request["views"]]),
    )
    complete = (
        result["annotation_status"] == "annotation_succeeded"
        and result["mapping_status"] == "complete"
    )
    states = result["parsed"]["states"] if result["parsed"] else []
    return dict(
        mapping_status="complete" if complete else "unknown",
        mapping_admitted=complete,
        annotation_status=result["annotation_status"],
        states=states,
        state_by_slot={sid: s["state_id"] for s in states for sid in s["slot_ids"]}
        if complete
        else {},
        chi_by_state={s["state_id"]: s["chi"] for s in states} if complete else {},
        deterministic_materialized_annotation=derived,
        error=result["error"],
    )


def _redundancy_proofs(extras, core, slots):
    proofs = []
    states = core.get("states")
    states = states if isinstance(states, list) else []
    for name, value in extras.items():
        accepted, rule = False, "unproved_auxiliary_content"
        if name == "slot_ids":
            accepted = (
                isinstance(value, list)
                and all(isinstance(s, str) for s in value)
                and len(value) == len(set(value))
                and set(value) == set(slots)
            )
            rule = "exact_complete_unique_original_member_set"
        elif name == "semantic_summary":
            accepted = isinstance(value, str) and (
                not value.strip()
                or value in [s.get("semantic_summary") for s in states if isinstance(s, dict)]
            )
            rule = "empty_or_exact_existing_core_summary"
        elif name == "partial_evidence":
            existing = [
                e
                for s in states
                if isinstance(s, dict)
                for e in s.get("partial_evidence", [])
                if isinstance(s.get("partial_evidence"), list)
            ]
            accepted = isinstance(value, list) and all(e in existing for e in value)
            rule = "empty_or_exact_existing_core_partial_evidence"
        proofs.append(
            dict(field=name, accepted=accepted, rule=rule, original_value_sha256=digest(value))
        )
    return proofs


def derive_mapping(record, source_ref):
    """Uniform zero-model interpretation, including unchanged original successes."""
    _checked_paid(record, source_ref, "mapping")
    request, artifact = record["request"], record["artifact"]
    raw, parsed, extras, core, proofs, errors = artifact["review_text"], None, {}, None, [], []
    inspection = dict(
        mapping_status="unknown",
        mapping_admitted=False,
        annotation_status="annotation_failed",
        states=[],
        state_by_slot={},
        chi_by_state={},
        deterministic_materialized_annotation=None,
        error=None,
    )
    try:
        require(
            artifact["finish_reason"] == "tool_calls" and not artifact["review_format_error"],
            "original annotation envelope incomplete",
        )
        require(isinstance(raw, str), "original mapping arguments absent")
        parsed = strict_json_decoder().decode(raw)
        require(
            isinstance(parsed, dict) and set(CORE_FIELDS) <= set(parsed),
            "complete original mapping core required",
        )
        core = {k: copy.deepcopy(parsed[k]) for k in CORE_FIELDS}
        extras = {k: copy.deepcopy(v) for k, v in parsed.items() if k not in CORE_FIELDS}
        proofs = _redundancy_proofs(extras, core, request["slot_ids"])
        require(all(p["accepted"] for p in proofs), "auxiliary content not mechanically redundant")
        inspection = _core_mapping(request, core)
        if inspection["error"]:
            errors.append(inspection["error"])
    except (ValueError, TypeError, KeyError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    original_success = (
        record["inspection"]["mapping_status"] == "complete"
        and record["inspection"]["mapping_admitted"] is True
    )
    unchanged = False
    if original_success:
        require(
            not errors and inspection["mapping_admitted"], "original successful mapping regressed"
        )
        unchanged = _semantic_fields(inspection) == _semantic_fields(record["inspection"])
        require(unchanged, "original state partition/evidence/chi changed")
        require(
            inspection["deterministic_materialized_annotation"]
            == record["inspection"]["deterministic_materialized_annotation"],
            "original complete materialized mapping changed",
        )
    return bound(
        dict(
            schema="v14_derived_mapping.v1",
            policy_id=policy_definition()["id"],
            task_id=record["task_id"],
            slot_ids=request["slot_ids"],
            source_record_ref=copy.deepcopy(source_ref),
            source_request_id=request["id"],
            source_inspection_id=record["inspection"]["id"],
            source_bindings=copy.deepcopy(request["source_bindings"]),
            raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest()
            if isinstance(raw, str)
            else None,
            auxiliary_sidecar=extras,
            auxiliary_proofs=proofs,
            core_original=core,
            inspection=inspection,
            usable=not errors and inspection["mapping_admitted"],
            errors=errors,
            original_success=original_success,
            core_unchanged_from_original_success=unchanged,
            original_semantic_sha256=digest(_semantic_fields(record["inspection"]))
            if original_success
            else None,
            derived_semantic_sha256=digest(_semantic_fields(inspection))
            if inspection["mapping_admitted"]
            else None,
            old_record_overwritten=False,
            raw_JSON_repaired=False,
            new_semantic_judgment=False,
            actual_model_calls=0,
            actual_model_call_receipt_verified=False,
            production_admitted=False,
        )
    )


def _union_character_count(spans):
    # Descriptive character count only. Never feed merged character ranges to tokenizer.
    by_segment = {}
    for span in spans:
        by_segment.setdefault(span["segment_id"], []).append((span["start"], span["end"]))
    total = 0
    for ranges in by_segment.values():
        right = -1
        for left, end in sorted(ranges):
            total += max(0, end - max(right, left))
            right = max(right, end)
    return total


def _positive_union(request, parsed):
    view, catalog = request["views"][0], request["domains"][0]["catalog"]
    require(
        all(p["quote"] for p in parsed["partial_positive_reason"]),
        "nonempty original partial quote required",
    )
    references = [dict(id=i, quote=None) for i in parsed["positive_reason_ids"]] + parsed[
        "partial_positive_reason"
    ]
    spans = [old.projection_semantics._locate(r, view, catalog) for r in references]
    require(
        all(s["kind"] == "public_content" for s in spans),
        "only public content for original positive union",
    )
    actions = old.projection_semantics._projection(
        dict(
            status=parsed["status"],
            positive_content=[],
            positive_actions=parsed["positive_action_ids"],
        ),
        view,
        catalog,
    )
    require(actions["usable"], actions["error"] or "projection status is not complete")
    return {
        **actions,
        "positive_content": spans,
        "positive_actions": actions["positive_actions"],
        "token_selection": TOKEN_SELECTION,
        "original_span_order_preserved": True,
        "character_spans_merged": False,
    }


def derive_projection(record, source_ref):
    _checked_paid(record, source_ref, "projection")
    request, artifact = record["request"], record["artifact"]
    raw, parsed, errors = old._decode(request, artifact)
    projection = None
    if not errors:
        try:
            projection = _positive_union(request, parsed)
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    usable = not errors and projection is not None
    original_errors = record["inspection"]["errors"]
    if usable and not record["inspection"]["usable"]:
        require(
            original_errors == ["overlapping_projection_decisions"],
            "only same-authority positive overlap can be derived",
        )
    raw_chars = sum(
        len(s["text"]) for s in request["views"][0]["segments"] if s["kind"] == "public_content"
    )
    positive = _union_character_count(projection["positive_content"]) if usable else None
    return bound(
        dict(
            schema="v14_derived_projection.v1",
            policy_id=policy_definition()["id"],
            task_id=record["task_id"],
            slot_id=record["slot_id"],
            source_record_ref=copy.deepcopy(source_ref),
            source_request_id=request["id"],
            source_inspection_id=record["inspection"]["id"],
            source_bindings=copy.deepcopy(request["source_bindings"]),
            raw_review_sha256=hashlib.sha256(raw.encode()).hexdigest()
            if isinstance(raw, str)
            else None,
            projection=projection,
            usable=usable,
            errors=errors,
            token_selection=TOKEN_SELECTION,
            reason_projection=dict(
                raw_public_characters=raw_chars,
                positive_public_characters=positive,
                all_public_reasoning_masked=(raw_chars > 0 and positive == 0) if usable else None,
            ),
            character_union_for_count_only=True,
            character_spans_merged=False,
            original_positive_spans_preserved=True,
            original_process_judgments_unchanged=True,
            old_record_overwritten=False,
            raw_JSON_repaired=False,
            actual_model_calls=0,
            actual_model_call_receipt_verified=False,
            production_admitted=False,
        )
    )


def _read(path, ref=None):
    path = Path(path)
    raw = path.read_bytes()
    value = json.loads(raw)
    own = dict(path=str(path.resolve()), id=value["id"], sha256=hashlib.sha256(raw).hexdigest())
    require(
        value["id"] == digest({k: v for k, v in value.items() if k != "id"}),
        "source content identity changed",
    )
    require(ref is None or own == ref, "source bytes/reference changed")
    return value, own


def _write(directory, value):
    path = Path(directory) / "record.json"
    if path.exists():
        existing, ref = _read(path)
        require(existing == value, "existing derived record differs; never overwrite")
        return ref
    persist(directory, value)
    return _read(path)[1]


def _source_hashes():
    names = (
        "v14_material_protocol.py",
        "v13_material_protocol.py",
        "v12_review_protocol.py",
        "v12_review_capacity.py",
        "v11_process_review.py",
        "v10_review_protocol.py",
        "v10_process_review.py",
        "qwen_protocol.py",
        "contracts.py",
        "v6_task.py",
    )
    return {n: hashlib.sha256((Path(__file__).parent / n).read_bytes()).hexdigest() for n in names}


def review_existing(source_root, output_root):
    """Root-only zero-model registration step; append new interpretation authorities."""
    protocol_hashes = _source_hashes()
    source, output = (
        Path(source_root).resolve(),
        Path(output_root).resolve() / "representation_review",
    )
    require(
        not (output / "summary/record.json").exists(),
        "never overwrite a completed representation review",
    )
    seal, seal_ref = _read(source / "completion_seal/record.json")
    plan, plan_ref = _read(source / "registration/record.json")
    definition, definition_ref = _read(source / "definition/record.json")
    require(
        seal["actual_returns"] == 1304
        and seal["mapping_complete_calls"] == 325
        and seal["registration_id"] == plan["id"]
        and plan["protocol_identity"] == definition["id"],
        "fixed complete V13 source required",
    )
    mappings, projection_derivations, inherited_projections, network, residual_projection = (
        [],
        [],
        [],
        [],
        [],
    )
    original_successes = 0
    for terminal_ref in seal["terminals"]:
        terminal, _ = _read(terminal_ref["path"], terminal_ref)
        record, ref = _read(terminal["record"]["path"], terminal["record"])
        if not record["actual_model_call_receipt_verified"]:
            require(record["purpose"] == "mapping", "unexpected source network purpose")
            network.append(
                dict(
                    task_id=record["task_id"],
                    record_ref=ref,
                    invocation_id=record["invocation_id"],
                    original_ledger_record_sha256=record["original_ledger_record_sha256"],
                )
            )
        elif record["purpose"] == "mapping":
            derived = derive_mapping(record, ref)
            original_successes += derived["original_success"]
            mappings.append(derived)
        elif record["inspection"]["usable"]:
            inherited_projections.append(
                dict(
                    slot_id=record["slot_id"],
                    task_id=record["task_id"],
                    authority_kind="V13_completion_only",
                    record=ref,
                )
            )
        else:
            derived = derive_projection(record, ref)
            projection_derivations.append(derived)
            if not derived["usable"]:
                residual_projection.append(record["slot_id"])
    require(
        len(mappings) == 633
        and original_successes == 325
        and len(network) == 12
        and len(projection_derivations) == 3
        and len(inherited_projections) == 668,
        "uniform entire source-return population required",
    )
    for pair in definition["pairs"]:
        if pair["projection_authority"] == "V12_A_original":
            inherited_projections.append(
                dict(
                    slot_id=pair["slot_id"],
                    task_id=pair["task_id"],
                    authority_kind="V12_A_original",
                    record=pair["A_record"],
                )
            )
    require(len(inherited_projections) == 2465, "all existing projection authorities retained")
    mapping_refs, all_mapping_refs, derived_projection_refs, all_projection_refs = [], [], [], []
    for value in mappings:
        ref = _write(output / "mappings" / digest(value["task_id"]), value)
        entry = dict(task_id=value["task_id"], authority_kind="V14_derived_mapping", record=ref)
        all_mapping_refs.append(entry)
        if value["usable"]:
            mapping_refs.append(entry)
    for value in projection_derivations:
        ref = _write(output / "projections" / digest(value["slot_id"]), value)
        entry = dict(
            task_id=value["task_id"],
            slot_id=value["slot_id"],
            authority_kind="V14_derived_overlap",
            record=ref,
        )
        all_projection_refs.append(entry)
        if value["usable"]:
            derived_projection_refs.append(entry)
    usable_tasks = {r["task_id"] for r in mapping_refs}
    residual_tasks = [
        j["task_id"]
        for j in plan["jobs"]
        if j["kind"] == "mapping" and j["task_id"] not in usable_tasks
    ]
    recovered = len(mapping_refs) - original_successes
    require(
        0 <= recovered <= 256 and len(residual_tasks) == 320 - recovered,
        "only fixed unresolved mapping support may be completed",
    )
    require(protocol_hashes == _source_hashes(), "representation code changed during review")
    result = bound(
        dict(
            schema="v14_representation_review.v1",
            policy=policy_definition(),
            source_v13_definition=definition_ref,
            source_v13_plan=plan_ref,
            source_v13_completion_seal=seal_ref,
            source_protocol_hashes=protocol_hashes,
            mapping_review_count=633,
            original_successes_preserved=325,
            original_success_partition_evidence_chi_unchanged=True,
            recovered_mapping_count=recovered,
            recovered_projection_count=len(derived_projection_refs),
            m=recovered,
            b=len(derived_projection_refs),
            mapping_authority_refs=mapping_refs,
            all_mapping_review_refs=all_mapping_refs,
            inherited_singleton_refs=plan["singletons"],
            inherited_projection_authority_refs=inherited_projections,
            derived_projection_authority_refs=derived_projection_refs,
            all_projection_review_refs=all_projection_refs,
            residual_mapping_task_ids=residual_tasks,
            residual_projection_slot_ids=residual_projection,
            network_unknown_task_ids=[n["task_id"] for n in network],
            network_unknown_sources=network,
            planned_unique_supplement_count=len(residual_tasks) + len(residual_projection),
            original_network_unknowns_and_holds_unchanged=True,
            original_records_overwritten=False,
            manual_interpretation_added=False,
            actual_model_calls=0,
            production_admitted=False,
        )
    )
    _write(output / "summary", result)
    return result


def _aliases(base):
    packages = {f"p{i}": v["slot_id"] for i, v in enumerate(base["views"])}
    actions = {}
    for i, local in enumerate(base["domains"]):
        available = (
            local["successful_action_ids"]
            if base["purpose"] == "projection"
            else [a["action_id"] for a in local["catalog"]["actions"]]
        )
        for j, action in enumerate(available):
            actions[("a" if base["purpose"] == "projection" else f"p{i}:a") + str(j)] = action
    return dict(packages=packages, actions=actions)


def _projection_tool(base, aliases):
    domains = {**base["domains"][0], "successful_action_ids": list(aliases["actions"])}
    return old.projection_tool(domains)


def _mapping_tool(base, aliases):
    obj, arr, enum = old._object, old._array, old._enum
    md = base["mapping_domains"]
    ev = enum(md["evidence_ids"], "original_nonempty_evidence")
    partial = obj(dict(id=ev, quote=dict(type="string")))
    intervention = obj(
        dict(
            kind=dict(type="string", enum=["verification", "revision"]),
            action=enum(list(aliases["actions"]), "actual_actions"),
            observation=enum(md["observation_ids"], "original_observations"),
            consequence=enum(md["consequence_ids"], "later_model_consequence"),
            partial_consequence_quote=dict(type="string"),
            effect=dict(type="string"),
        )
    )
    return old._tool(
        dict(
            mapping_status=dict(type="string", enum=["complete", "unknown"]),
            states=arr(
                obj(
                    dict(
                        members=arr(enum(list(aliases["packages"]), "short_packages")),
                        semantic_summary=dict(type="string"),
                        evidence_ids=arr(ev),
                        partial_evidence=arr(partial),
                        chi=dict(type="integer", enum=[0, 1]),
                        chi_reason=dict(type="string"),
                        interventions=arr(intervention),
                    )
                )
            ),
            ambiguity_notes=arr(
                obj(
                    dict(
                        description=dict(type="string"),
                        evidence_ids=arr(ev),
                        partial_evidence=arr(partial),
                    )
                )
            ),
        )
    )


MAPPING_RUBRIC = """Partition the complete supplied original task into semantic behavior
states. Return one submit_material object with exactly mapping_status, states,
ambiguity_notes. Package aliases p0,p1,... are fixed original complete trajectories.
Express membership ONCE, only as each state's members. Never output slot_ids or a
state_id anywhere. Host will generate canonical state IDs without changing membership.
Every package must belong to exactly one state in a complete partition. Never split
a trajectory into its steps, assign a package twice, omit it, or repair ambiguity by
inventing singleton states. If unresolved, say mapping_status=unknown and describe it
in ambiguity_notes with original evidence; notes cannot coexist with a complete map.
semantic_summary and partial_evidence belong inside their state, NEVER at top level.
States compare evidence choice, derivation, interpretation of original observations,
and consequential actual verification/revision. Wording, length, IDs, tool counts or
mere run-versus-submit patterns do not establish different semantic states.
Evidence IDs select original nonempty units. Partial quotes must be nonempty, exact,
unique in their original segment and within the chosen unit. Never compute offsets.
For chi=1 give a real consequential intervention for every state member, using the
provided SHORT action alias, its true observation ID, a later model consequence ID,
and effect. Empty partial_consequence_quote means whole consequence unit. Ordinary
execution, a claim of checking, or repetition alone is not consequential verification.
chi=0 must have no interventions. No alternate partition or fabricated evidence.
Read the complete histories, including sources/errors/withdrawals; not supervision.
"""

PROJECTION_RUBRIC = (
    old.PROJECTION_RUBRIC
    + """
V14 uses SHORT action aliases a0,a1,... in positive_action_ids. Select only these
provided aliases; Host resolves them to the exact original successful action.
Keep every original approved span. Repeated positive spans have idempotent Boolean
token selection, not repeated loss and not enlarged character intervals.
"""
)


def _compact_capacity(base, aliases):
    if base["purpose"] == "projection":
        local = base["domains"][0]
        units = {u["unit_id"]: u for u in local["catalog"]["units"]}
        scenario = dict(
            status="complete",
            positive_reason_ids=local["reason_ids"],
            partial_positive_reason=[
                dict(id=i, quote=units[i]["text"]) for i in local["reason_ids"]
            ],
            positive_action_ids=list(aliases["actions"]),
        )
    else:
        states = []
        for i, local in enumerate(base["domains"]):
            prefix = f"p{i}:"
            refs = [r for r in base["mapping_domains"]["evidence_ids"] if r.startswith(prefix)]
            longest = sorted(
                (u for u in local["catalog"]["units"] if u["text"]),
                key=lambda u: len(canonical(u["text"])),
                reverse=True,
            )[:4]
            obs = [r for r in base["mapping_domains"]["observation_ids"] if r.startswith(prefix)]
            consequences = [
                r for r in base["mapping_domains"]["consequence_ids"] if r.startswith(prefix)
            ]
            states.append(
                dict(
                    members=[f"p{i}"],
                    semantic_summary="x" * 1024,
                    evidence_ids=refs,
                    partial_evidence=[
                        dict(id=prefix + u["unit_id"], quote=u["text"]) for u in longest
                    ],
                    chi=1,
                    chi_reason="x" * 1024,
                    interventions=[
                        dict(
                            kind="verification",
                            action=a,
                            observation=obs[0] if obs else "",
                            consequence=consequences[0] if consequences else "",
                            partial_consequence_quote="",
                            effect="x" * 512,
                        )
                        for a in aliases["actions"]
                        if a.startswith(prefix)
                    ],
                )
            )
        scenario = dict(mapping_status="complete", states=states, ambiguity_notes=[])
    size = len(canonical(scenario)) + 1024
    estimate = (5 * size + 3) // 4
    cap = next((n for n in old.CAPS if n >= estimate), None)
    require(cap is not None, "new compact response exceeds allowed capacity; no clipping")
    return dict(
        schema="v14_serialized_response_capacity.v1",
        scenario_sha256=digest(scenario),
        scenario_utf8_bytes=size - 1024,
        tool_envelope_utf8_bytes=1024,
        estimated_output_requirement=estimate,
        max_output_tokens=cap,
        safety_multiplier="5/4",
        exact_token_forecast=False,
        hard_output_size_guarantee=False,
        planning_scenario_is_not_annotation=True,
    )


def _prepare(views, purpose, protocol_id, source_bindings):
    require(purpose in {"projection", "mapping"}, "only registered residual material purposes")
    base = old._prepare(views, purpose, protocol_id, source_bindings)
    aliases = _aliases(base)
    tool = (
        _projection_tool(base, aliases) if purpose == "projection" else _mapping_tool(base, aliases)
    )
    packages = []
    for i, (view, local) in enumerate(zip(base["views"], base["domains"], strict=True)):
        payload = old.public_payload(view, local["catalog"], purpose)
        payload.update(wire_protocol=WIRE, package_alias=f"p{i}")
        packages.append(payload)
    public_domains = (
        {k: base["domains"][0][k] for k in ("evidence_ids", "reason_ids")}
        if purpose == "projection"
        else base["mapping_domains"]
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
                    task_id=base["task_id"],
                    packages=packages,
                    aliases=aliases,
                    selectable_domains=public_domains,
                )
            ).decode(),
        ),
    ]
    cap = _compact_capacity(base, aliases)
    request = {k: v for k, v in base.items() if k != "id"}
    request.update(
        schema="v14_material_request.v1",
        wire_protocol=WIRE,
        batch_id=BATCH_ID,
        policy_id=policy_definition()["id"],
        aliases=aliases,
        messages=messages,
        strict_tool=tool,
        capacity=cap,
        max_output_tokens=cap["max_output_tokens"],
        episode_id="v14" + base["episode_id"][3:],
    )
    request = bound(request)
    require(
        len(canonical(_body(request))) + request["max_output_tokens"] < old.CONTEXT_CEILING,
        "complete public body/context envelope exceeded; no truncation",
    )
    return request


def prepare_projection(view, *, protocol_id, source_bindings):
    return _prepare([view], "projection", protocol_id, source_bindings)


def prepare_mapping(views, *, protocol_id, source_bindings):
    return _prepare(views, "mapping", protocol_id, source_bindings)


def checked_request(request):
    require(request.get("model") == MODEL, "V14 model must remain deepseek-flash")
    require(
        request
        == _prepare(
            request["views"], request["purpose"], request["protocol_id"], request["source_bindings"]
        ),
        "registered original V14 request changed",
    )
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


def _decode(request, artifact):
    checked_request(request)
    raw, parsed, errors = artifact["review_text"], None, []
    if not isinstance(raw, str):
        errors.append("missing_material_argument_text")
    else:
        try:
            parsed = strict_json_decoder().decode(raw)
            old._validate_wire(parsed, request["strict_tool"]["function"]["parameters"])
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    if artifact["finish_reason"] != "tool_calls" or artifact.get("review_format_error"):
        errors.append("original_annotation_envelope_incomplete:" + str(artifact["finish_reason"]))
    return raw, parsed, errors


def _expand_mapping(request, parsed):
    members_seen, ordered = [], []
    aliases = request["aliases"]
    for state in parsed["states"]:
        members = state["members"]
        require(
            members and len(members) == len(set(members)), "nonempty unique state members required"
        )
        members_seen.extend(members)
        ordered.append((min(int(m[1:]) for m in members), state))
    require(
        len(members_seen) == len(set(members_seen)), "one original package cannot be in two states"
    )
    if parsed["mapping_status"] == "complete":
        require(
            set(members_seen) == set(aliases["packages"]) and not parsed["ambiguity_notes"],
            "complete partition requires all original members and no ambiguity",
        )
    else:
        require(parsed["ambiguity_notes"], "unknown partition must preserve stated ambiguity")
    result = dict(mapping_status=parsed["mapping_status"], states=[], ambiguities=[])
    for index, (_, state) in enumerate(sorted(ordered, key=lambda p: p[0])):
        value = dict(
            state_id=f"z{index:04d}",
            slot_ids=[
                aliases["packages"][p] for p in sorted(state["members"], key=lambda p: int(p[1:]))
            ],
            **{
                k: copy.deepcopy(state[k])
                for k in (
                    "semantic_summary",
                    "evidence_ids",
                    "partial_evidence",
                    "chi",
                    "chi_reason",
                )
            },
            interventions=[],
        )
        for intervention in state["interventions"]:
            action_alias = intervention["action"]
            package_alias = action_alias.split(":", 1)[0]
            require(
                package_alias in state["members"], "intervention action must belong to its state"
            )
            value["interventions"].append(
                dict(
                    slot_id=aliases["packages"][package_alias],
                    action_id=aliases["actions"][action_alias],
                    kind=intervention["kind"],
                    observation_id=intervention["observation"],
                    consequence_id=intervention["consequence"],
                    partial_consequence_quote=intervention["partial_consequence_quote"],
                    effect=intervention["effect"],
                )
            )
        result["states"].append(value)
    for note in parsed["ambiguity_notes"]:
        result["ambiguities"].append(dict(slot_ids=request["slot_ids"], **copy.deepcopy(note)))
    return result


def inspect_reply(request, artifact):
    raw, parsed, errors = _decode(request, artifact)
    common = dict(
        request_id=request["id"],
        protocol_id=request["protocol_id"],
        task_id=request["task_id"],
        source_bindings=request["source_bindings"],
        raw_review=raw,
        raw_wire_annotation=parsed,
        original_process_judgments_unchanged=True,
        JSON_repaired=False,
        actual_model_call_receipt_verified=False,
        production_admitted=False,
        semantic_truth_proved=False,
    )
    if request["purpose"] == "projection":
        projection, derived = None, None
        if not errors:
            try:
                derived = {
                    **copy.deepcopy(parsed),
                    "positive_action_ids": [
                        request["aliases"]["actions"][a] for a in parsed["positive_action_ids"]
                    ],
                }
                projection = _positive_union(request, derived)
            except (ValueError, TypeError, KeyError) as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        usable = not errors and projection is not None
        raw_chars = sum(
            len(s["text"]) for s in request["views"][0]["segments"] if s["kind"] == "public_content"
        )
        positive = _union_character_count(projection["positive_content"]) if usable else None
        return bound(
            dict(
                schema="v14_projection_inspection.v1",
                **common,
                slot_id=request["slot_id"],
                projection=projection,
                usable=usable,
                errors=errors,
                token_selection=TOKEN_SELECTION,
                deterministic_materialized_annotation=derived,
                reason_projection=dict(
                    raw_public_characters=raw_chars,
                    positive_public_characters=positive,
                    all_public_reasoning_masked=(raw_chars > 0 and positive == 0)
                    if usable
                    else None,
                ),
            )
        )
    result, expanded = None, None
    if not errors:
        try:
            expanded = _expand_mapping(request, parsed)
            # The new typed wire is already checked; retain original semantic/locator contract.
            materialized = old._materialize_mapping(request, expanded)
            result = old.mapping_semantics._inspect_mapping(
                canonical(materialized).decode(),
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
            schema="v14_mapping_inspection.v1",
            **common,
            slot_ids=request["slot_ids"],
            mapping_status="complete" if complete else "unknown",
            mapping_admitted=complete,
            annotation_status="annotation_succeeded" if not errors else "annotation_failed",
            states=states,
            state_by_slot={sid: s["state_id"] for s in states for sid in s["slot_ids"]}
            if complete
            else {},
            chi_by_state={s["state_id"]: s["chi"] for s in states} if complete else {},
            chi_status="semantically_annotated" if complete else "unknown",
            deterministic_singleton=False,
            deterministic_materialized_annotation=materialized if result is not None else None,
            deterministic_expanded_wire=expanded,
            state_IDs_generated_by_host=True,
            errors=errors,
            no_ambiguous_package_dropped=True,
        )
    )


inspect_paid_annotation = inspect_reply


def validate_inspection(inspection, request, artifact):
    require(
        inspection == inspect_reply(request, artifact),
        "material inspection changed from original response",
    )
    return inspection
