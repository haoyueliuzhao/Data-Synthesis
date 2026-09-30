"""Append-only, state-independent encoding cache; never grants training admission.

The population is fixed once at 2468 originals / 744 tasks. Initial 2465 known
authorities can be encoded before mapping finishes. Later revisions append only
pending authorities; successful material is never selected into a smaller pool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
from collections import Counter
from importlib.metadata import version
from pathlib import Path

from .contracts import Episode, digest
from .providers import tokenizer_binding
from .storage import read_json
from .v6_collection import bound, persist, require
from .v6_task import public_trajectory_view
from .v7_base_evaluation import ORIGIN, load_tokenizer
from .v14_student_encoding import (
    CONTEXT_LIMIT,
    ENCODING_POLICY,
    ENCODING_SCHEMA,
    encode_for_student,
    supervision_manifest,
)

STUDY = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
)
SOURCE = STUDY / "v13_material_02"
OUTPUT = STUDY / "v14_representation_01/encoding_cache"
REGISTRATION_SCHEMA = "v14_state_independent_encoding_registration.v1"
REVISION_SCHEMA = "v14_append_only_encoding_authorities.v1"
SOURCES = (
    "v14_student_encoding.py",
    "v14_encoding_cache.py",
    "v6_encoding.py",
    "v6_task.py",
    "encoding.py",
    "providers.py",
    "contracts.py",
    "v7_base_evaluation.py",
)
_WORKER = None


def source_bindings():
    root = Path(__file__).parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCES}


def checked(value, schema=None):
    require(
        isinstance(value, dict)
        and value.get("id") == digest({k: v for k, v in value.items() if k != "id"})
        and (schema is None or value.get("schema") == schema),
        "immutable cache/source identity changed",
    )
    return value


def entry(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    value = json.loads(raw)
    return dict(
        path=str(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        id=value.get("id", value.get("encoding_id")),
    )


def read_ref(ref):
    raw = Path(ref["path"]).read_bytes()
    value = json.loads(raw)
    require(
        hashlib.sha256(raw).hexdigest() == ref["sha256"]
        and value.get("id", value.get("encoding_id")) == ref["id"],
        "referenced original/cache bytes changed",
    )
    return value


def _episode(ref, task_id):
    raw = Path(ref["path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "original episode file changed")
    episode = Episode.model_validate_json(raw)
    require(
        digest(episode) == ref["episode_sha256"] and episode.task_id == task_id,
        "original episode identity/task changed",
    )
    return episode


def _check_episode_bytes(ref):
    require(
        hashlib.sha256(Path(ref["path"]).read_bytes()).hexdigest() == ref["sha256"],
        "cached original episode bytes changed",
    )


def _projection(authority_ref, kind, pair):
    record = checked(read_ref(authority_ref))
    if kind == "V12_A_original":
        require(
            authority_ref == pair["A_record"]
            and record["actual_model_call_receipt_verified"] is True
            and record["new_pipeline_outcomes"]["projection_usable"] is True,
            "original usable V12 A remains the unique authority",
        )
        projection = record["inspection"]["auxiliary"]["supervision"]
        view = record["request"]["candidate_request"]["trajectory"]
    elif kind in {"V13_completion_only", "V14_completion_only"}:
        expected = (
            "v13_paid_material_annotation.v1"
            if kind == "V13_completion_only"
            else "v14_paid_material_annotation.v1"
        )
        require(
            record["schema"] == expected
            and record["actual_model_call_receipt_verified"] is True
            and record["inspection"].get("usable") is True,
            "new projection authority needs its actual admitted settled annotation",
        )
        projection = record["inspection"]["projection"]
        view = record["request"]["views"][0]
        require(
            len(record["request"]["views"]) == 1 and record["request"]["purpose"] == "projection",
            "projection request cannot substitute a mapping or another original",
        )
    else:
        require(
            kind == "V14_derived_overlap"
            and record["schema"] == "v14_derived_projection.v1"
            and record["usable"] is True
            and record["token_selection"] == "union_of_individually_bounded_original_spans",
            "explicit source-bound overlap interpretation required",
        )
        original = checked(read_ref(record["source_record_ref"]))
        require(
            original["schema"] == "v13_paid_material_annotation.v1"
            and original["actual_model_call_receipt_verified"] is True
            and record["source_request_id"] == original["request"]["id"],
            "derived projection must preserve its actual original annotation source",
        )
        projection, view = record["projection"], original["request"]["views"][0]
    require(
        view["slot_id"] == pair["slot_id"] and view["task_id"] == pair["task_id"],
        "authority points at a different fixed original",
    )
    return projection, view


def _cache_key(registration, original, manifest):
    return digest(
        dict(
            schema="v14_state_independent_cache_key.v1",
            episode_sha256=original["episode_sha256"],
            episode_file_sha256=original["sha256"],
            supervision_manifest_sha256=digest(manifest),
            authority_record=manifest["authority_record"],
            tokenizer_binding=registration["tokenizer_binding"],
            context_limit=CONTEXT_LIMIT,
            encoding_policy=ENCODING_POLICY,
            encoding_source_bindings=registration["encoding_source_bindings"],
            tokenizer_runtime=registration["tokenizer_runtime"],
        )
    )


def _authority_entry(output, registration, pair, ref, kind):
    projection, view = _projection(ref, kind, pair)
    episode = _episode(pair["original_episode"], pair["task_id"])
    require(
        view == public_trajectory_view(episode, slot_id=pair["slot_id"]),
        "authority must retain complete original public history",
    )
    manifest = supervision_manifest(
        episode,
        slot_id=pair["slot_id"],
        authority_record=ref,
        projection=projection,
        population_id=registration["population_id"],
        projection_authority=kind,
    )
    key = _cache_key(registration, pair["original_episode"], manifest)
    path = output / "manifests" / key / "record.json"
    persist(path.parent, manifest)
    return dict(
        slot_id=pair["slot_id"],
        task_id=pair["task_id"],
        cache_key=key,
        original_episode=pair["original_episode"],
        supervision_manifest=entry(path),
        authority_record=ref,
        projection_authority=kind,
    )


def _registration(output):
    output = Path(output).resolve()
    registration = checked(read_json(output / "registration/record.json"), REGISTRATION_SCHEMA)
    require(
        registration["encoding_source_bindings"] == source_bindings(),
        "encoding source changed after registration; never reuse stale policy output",
    )
    require(
        registration["tokenizer_runtime"]
        == {n: version(n) for n in ("tokenizers", "transformers")},
        "registered tokenizer runtime changed",
    )
    definition = checked(
        read_ref(registration["source_definition"]), "v13_fixed_candidate_population.v1"
    )
    require(
        definition["id"] == registration["population_id"]
        and definition["candidate_slot_ids"] == registration["candidate_slot_ids"]
        and len(registration["candidate_slot_ids"]) == 2468
        and len(registration["fixed_task_slots"]) == 744,
        "cache must retain the complete fixed population",
    )
    return registration, definition


def _revisions(output, registration):
    directory = Path(output) / "revisions"
    paths = (
        sorted(p / "record.json" for p in directory.iterdir() if p.is_dir())
        if directory.exists()
        else []
    )
    revisions, authorities, prior_ref = [], {}, None
    fixed = set(registration["candidate_slot_ids"])
    for index, path in enumerate(paths):
        revision = checked(read_json(path), REVISION_SCHEMA)
        require(
            path.parent.name == f"{index:04d}"
            and revision["index"] == index
            and revision["registration_id"] == registration["id"]
            and revision["previous_revision"] == prior_ref,
            "append-only authority revision chain changed",
        )
        for item in revision["added_authorities"]:
            sid = item["slot_id"]
            require(
                sid in fixed and sid not in authorities,
                "only unresolved authority slots may be appended",
            )
            authorities[sid] = item
        pending = [s for s in registration["candidate_slot_ids"] if s not in authorities]
        require(
            revision["pending_slot_ids"] == pending
            and revision["known_authority_count"] == len(authorities),
            "revision must preserve full-population unresolved inventory",
        )
        prior_ref = entry(path)
        revisions.append(revision)
    return revisions, authorities


def prepare(output=OUTPUT, *, source_v13=SOURCE):
    """Freeze initial 2465 known authorities and pending3; encode nothing yet."""
    output, source = Path(output).resolve(), Path(source_v13).resolve()
    require(
        not (output / "registration/record.json").exists(),
        "cache registration already exists; use existing immutable registration",
    )
    definition_ref = entry(source / "definition/record.json")
    definition = checked(read_ref(definition_ref), "v13_fixed_candidate_population.v1")
    seal_ref = entry(source / "completion_seal/record.json")
    seal = checked(read_ref(seal_ref), "v13_material_completion_seal.v1")
    source_plan_ref = entry(source / "registration/record.json")
    source_plan = checked(read_ref(source_plan_ref))
    require(
        seal["protocol_id"] == definition["id"] == source_plan["protocol_identity"]
        and seal["registration_id"] == source_plan["id"]
        and seal["all_registered_jobs_have_authentic_terminals"] is True
        and seal["projection_usable_calls"] == 668
        and len(definition["pairs"]) == 2468,
        "initial cache uses completed V13 fixed population and its 2465 existing authorities",
    )
    original_plan = checked(read_ref(definition["inputs"]["source_v10_plan"]))
    assets_ref = entry(ORIGIN)
    assets = checked(read_ref(assets_ref))
    require(
        assets["id"] == original_plan["original"]["prior_original_protocol_id"],
        "unchanged original Student assets required",
    )
    tokenizer = load_tokenizer(assets["assets"])
    registration = bound(
        dict(
            schema=REGISTRATION_SCHEMA,
            population_id=definition["id"],
            source_v13_root=str(source),
            source_definition=definition_ref,
            source_registration=source_plan_ref,
            source_completion_seal=seal_ref,
            candidate_slot_ids=definition["candidate_slot_ids"],
            fixed_task_slots=definition["fixed_task_slots"],
            fixed_packages=2468,
            fixed_tasks=744,
            initial_expected_known=2465,
            initial_expected_pending=3,
            original_student_assets=assets_ref,
            tokenizer_binding=list(tokenizer_binding(tokenizer)),
            tokenizer_runtime={n: version(n) for n in ("tokenizers", "transformers")},
            context_limit=CONTEXT_LIMIT,
            context_truncation=False,
            encoding_policy=ENCODING_POLICY,
            encoding_source_bindings=source_bindings(),
            maximum_cpu_workers=8,
            API_calls=0,
            GPU_used=False,
            state_independent=True,
            mapping_completion_required_for_encoding=False,
            all_fixed_material_required_for_training=True,
            training_authorized=False,
        )
    )
    # This prospective registration precedes any production encoding.
    persist(output / "registration", registration)
    projection_records = {}
    require(
        len(seal["terminals"]) == len(source_plan["jobs"]) == 1316,
        "complete source terminal roster required",
    )
    for job, terminal_ref in zip(source_plan["jobs"], seal["terminals"], strict=True):
        if job["purpose"] != "projection":
            continue
        terminal = checked(read_ref(terminal_ref))
        require(terminal["episode_id"] == job["episode_id"], "source terminal order changed")
        if terminal["terminal_kind"] == "paid_model_return":
            record = checked(read_ref(terminal["record"]))
            if record["inspection"]["usable"]:
                projection_records[job["slot_id"]] = terminal["record"]
    added = []
    for pair in definition["pairs"]:
        sid = pair["slot_id"]
        if pair["projection_authority"] == "V12_A_original":
            ref, kind = pair["A_record"], "V12_A_original"
        elif sid in projection_records:
            ref, kind = projection_records[sid], "V13_completion_only"
        else:
            continue
        added.append(_authority_entry(output, registration, pair, ref, kind))
    require(
        len(added) == 2465, "all known source authorities must be frozen without mapping selection"
    )
    known = {a["slot_id"] for a in added}
    revision = bound(
        dict(
            schema=REVISION_SCHEMA,
            registration_id=registration["id"],
            index=0,
            previous_revision=None,
            added_authorities=added,
            known_authority_count=len(added),
            pending_slot_ids=[s for s in registration["candidate_slot_ids"] if s not in known],
            predeclared_authority_selection=True,
            state_independent=True,
            training_authorized=False,
        )
    )
    persist(output / "revisions/0000", revision)
    return revision


def append_authorities(output, authorities):
    """Append exact derived/new source refs for pending slots; never replace prior masks."""
    output = Path(output).resolve()
    registration, definition = _registration(output)
    revisions, known = _revisions(output, registration)
    require(
        bool(revisions) and isinstance(authorities, list) and bool(authorities),
        "existing initial inventory and nonempty additions required",
    )
    pairs = {p["slot_id"]: p for p in definition["pairs"]}
    supplied = {a["slot_id"]: a for a in authorities}
    require(
        len(supplied) == len(authorities) and set(supplied) <= set(pairs) - set(known),
        "append only the still-pending fixed authority slots, no replacement or best-of",
    )
    added = []
    for sid in registration["candidate_slot_ids"]:
        if sid not in supplied:
            continue
        row = supplied[sid]
        require(
            row["projection_authority"] in {"V14_derived_overlap", "V14_completion_only"},
            "a pending V13 failure needs its explicitly registered V14 authority",
        )
        added.append(
            _authority_entry(
                output,
                registration,
                pairs[sid],
                row["authority_record"],
                row["projection_authority"],
            )
        )
    index = len(revisions)
    known_slots = set(known) | set(supplied)
    revision = bound(
        dict(
            schema=REVISION_SCHEMA,
            registration_id=registration["id"],
            index=index,
            previous_revision=entry(output / "revisions" / f"{index - 1:04d}" / "record.json"),
            added_authorities=added,
            known_authority_count=len(known_slots),
            pending_slot_ids=[
                s for s in registration["candidate_slot_ids"] if s not in known_slots
            ],
            predeclared_authority_selection=True,
            state_independent=True,
            training_authorized=False,
        )
    )
    persist(output / "revisions" / f"{index:04d}", revision)
    return revision


def _checked_encoding(value, item, registration, manifest):
    require(
        value.get("schema") in {ENCODING_SCHEMA, "v14_encoding_failure.v1"},
        "unknown encoding result schema",
    )
    if value["schema"] == "v14_encoding_failure.v1":
        checked(value)
        require(
            value["cache_key"] == item["cache_key"] and value["encoding_admitted"] is False,
            "failure must remain bound to this immutable cache key",
        )
        return value
    require(
        value.get("encoding_id")
        == "v14_student_encoding:" + digest({k: v for k, v in value.items() if k != "encoding_id"})
        and value["episode_sha256"] == item["original_episode"]["episode_sha256"]
        and value["supervision_manifest_sha256"] == digest(manifest)
        and value["authority_record"] == item["authority_record"]
        and [value["tokenizer_digest"], value["chat_template_digest"]]
        == registration["tokenizer_binding"]
        and value["context_limit"] == 24576
        and value["context_truncated"] is False
        and value["state_or_chi_used"] is False
        and value["training_authorized"] is False,
        "cache encoding source/authority/tokenizer/context identity differs",
    )
    count = 0
    for row in value["rows"]:
        require(
            row["row_sha256"] == digest({k: v for k, v in row.items() if k != "row_sha256"}),
            "cached row changed",
        )
        ids, positions = row["input_ids"], row["target_positions"]
        require(
            positions == sorted(set(positions))
            and row["target_ids"] == [ids[p] for p in positions]
            and sorted(p for values in row["layer_target_positions"].values() for p in values)
            == positions,
            "cache targets must be the unique partitioned original positions",
        )
        count += len(positions)
    require(
        count == value["L_P"] == value["total_supervised_tokens"],
        "whole-package denominator changed",
    )
    return value


def _worker_init(tokenizer):
    global _WORKER
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    _WORKER = tokenizer


def _encode_item(item):
    episode = _episode(item["original_episode"], item["task_id"])
    manifest = checked(read_ref(item["supervision_manifest"]))
    try:
        return encode_for_student(episode, manifest, _WORKER)
    except (ValueError, TypeError, KeyError) as exc:
        return bound(
            dict(
                schema="v14_encoding_failure.v1",
                slot_id=item["slot_id"],
                cache_key=item["cache_key"],
                encoding_admitted=False,
                encoding_started=True,
                failures=[
                    dict(reason="lossless_encoding_failed", error=f"{type(exc).__name__}: {exc}")
                ],
                training_authorized=False,
            )
        )


def run(output=OUTPUT, *, workers=8):
    """Encode only missing cache keys from the latest append-only authority revision."""
    output = Path(output).resolve()
    registration, _ = _registration(output)
    revisions, authorities = _revisions(output, registration)
    require(
        revisions and type(workers) is int and 1 <= workers <= 8,
        "frozen authority revision and 1..8 CPU workers required",
    )
    assets = checked(read_ref(registration["original_student_assets"]))
    tokenizer = load_tokenizer(assets["assets"])
    require(
        list(tokenizer_binding(tokenizer)) == registration["tokenizer_binding"],
        "actual Student tokenizer/template changed",
    )
    pending, cached = [], {}
    for sid in registration["candidate_slot_ids"]:
        if sid not in authorities:
            continue
        item = authorities[sid]
        manifest = checked(read_ref(item["supervision_manifest"]))
        require(
            _cache_key(registration, item["original_episode"], manifest) == item["cache_key"],
            "cache key changed",
        )
        read_ref(item["authority_record"])
        _check_episode_bytes(item["original_episode"])
        path = output / "encodings" / item["cache_key"] / "record.json"
        if path.exists():
            _checked_encoding(read_json(path), item, registration, manifest)
            cached[sid] = entry(path)
        else:
            pending.append(item)
    if pending:
        with multiprocessing.get_context("fork").Pool(
            min(workers, len(pending)), initializer=_worker_init, initargs=(tokenizer,)
        ) as pool:
            for item, value in zip(
                pending, pool.imap(_encode_item, pending, chunksize=1), strict=True
            ):
                path = output / "encodings" / item["cache_key"] / "record.json"
                persist(path.parent, value)
                cached[item["slot_id"]] = entry(path)
    require(
        set(cached) == set(authorities),
        "every currently explicit authority needs an outcome; no success-only subset",
    )
    result = bound(
        dict(
            schema="v14_encoding_cache_run.v1",
            registration_id=registration["id"],
            authority_revision=entry(
                output / "revisions" / f"{len(revisions) - 1:04d}" / "record.json"
            ),
            encoding_refs={s: cached[s] for s in registration["candidate_slot_ids"] if s in cached},
            known_authority_count=len(authorities),
            pending_authority_slot_ids=revisions[-1]["pending_slot_ids"],
            all_known_authorities_have_encoding_outcome=True,
            full_population_size=2468,
            API_calls=0,
            GPU_used=False,
            state_independent=True,
            training_authorized=False,
        )
    )
    persist(output / "runs" / revisions[-1]["id"], result)
    return result


def load_cache(output=OUTPUT, *, require_complete=False):
    """Consume immutable cached outcomes, not state assignments or training permission."""
    output = Path(output).resolve()
    registration, definition = _registration(output)
    revisions, authorities = _revisions(output, registration)
    require(bool(revisions), "registered authorities required")
    run_record = checked(
        read_json(output / "runs" / revisions[-1]["id"] / "record.json"),
        "v14_encoding_cache_run.v1",
    )
    require(
        run_record["registration_id"] == registration["id"]
        and run_record["authority_revision"]
        == entry(output / "revisions" / f"{len(revisions) - 1:04d}" / "record.json")
        and set(run_record["encoding_refs"]) == set(authorities),
        "encoding run does not cover the latest fixed authority revision",
    )
    encodings, manifests = {}, {}
    for sid, item in authorities.items():
        manifest = checked(read_ref(item["supervision_manifest"]))
        require(
            _cache_key(registration, item["original_episode"], manifest) == item["cache_key"],
            "authority/cache identity changed",
        )
        read_ref(item["authority_record"])
        _check_episode_bytes(item["original_episode"])
        encodings[sid] = _checked_encoding(
            read_ref(run_record["encoding_refs"][sid]), item, registration, manifest
        )
        manifests[sid] = manifest
    failed = [s for s, e in encodings.items() if not e["encoding_admitted"]]
    complete = len(authorities) == 2468 and not failed
    require(
        not require_complete or complete,
        "training material still requires every one of 2468 encodable original packages",
    )
    layers = Counter(reason=0, tool=0, final=0)
    for encoded in encodings.values():
        layers.update(encoded.get("layer_target_counts", {}))
    return dict(
        registration=registration,
        task_ids=[row["task_id"] for row in definition["tasks"]],
        slot_ids=registration["candidate_slot_ids"],
        authority_revision=revisions[-1],
        authorities=authorities,
        encodings=encodings,
        manifests=manifests,
        encoding_refs=run_record["encoding_refs"],
        encoding_entries=run_record["encoding_refs"],
        manifest_refs={s: item["supervision_manifest"] for s, item in authorities.items()},
        manifest_entries={s: item["supervision_manifest"] for s, item in authorities.items()},
        pending_slot_ids=revisions[-1]["pending_slot_ids"],
        failed_encoding_slot_ids=failed,
        complete_encoding_population=complete,
        full_population_size=2468,
        known_encoded_count=len(encodings),
        observed_layer_target_counts=dict(layers),
        full_population_layer_target_counts=dict(layers) if complete else None,
        tokenizer_binding=tuple(registration["tokenizer_binding"]),
        run=run_record,
        run_ref=entry(output / "runs" / revisions[-1]["id"] / "record.json"),
        training_authorized=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "inspect", "append"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--source-v13", type=Path, default=SOURCE)
    parser.add_argument("--authorities", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    if args.action == "prepare":
        result = prepare(args.output, source_v13=args.source_v13)
    elif args.action == "run":
        result = run(args.output, workers=args.workers)
    elif args.action == "append":
        require(args.authorities is not None, "append requires explicit authority source list")
        result = append_authorities(args.output, read_json(args.authorities))
    else:
        result = load_cache(args.output)
        result = {
            k: v
            for k, v in result.items()
            if k not in {"encodings", "manifests", "authorities", "registration", "run"}
        }
    summary = {
        k: result[k]
        for k in (
            "schema",
            "id",
            "known_authority_count",
            "known_encoded_count",
            "pending_slot_ids",
            "pending_authority_slot_ids",
            "failed_encoding_slot_ids",
            "complete_encoding_population",
            "training_authorized",
        )
        if k in result
    }
    summary["output"] = str(args.output.resolve())
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
