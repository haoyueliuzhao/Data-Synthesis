"""Only V14 encoding/cache boundary controls; synthetic authorities, zero API/GPU."""

import copy
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_finance_v9_conditional_training import driver as cpu_driver
from test_finance_v10_process_review import fixture
from test_finance_v10_student_encoding import manifest as old_manifest
from test_finance_v10_student_encoding import tokenizer as tokenizer

from trusted_synthesis.finance_research import v10_training
from trusted_synthesis.finance_research import v14_encoding_cache as cache
from trusted_synthesis.finance_research import v14_student_encoding as encoding
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.providers import tokenizer_binding
from trusted_synthesis.finance_research.v6_collection import bound, persist
from trusted_synthesis.finance_research.v6_task import public_trajectory_view
from trusted_synthesis.finance_research.v10_student_encoding import (
    encode_process_review_for_student as old_encode,
)


def inputs():
    episode, request, body = fixture()
    old = old_manifest(request, body)
    projection = dict(
        usable=True,
        positive_content=[
            dict(
                segment_id=s["original_segment_id"],
                start=s["start"],
                end=s["end"],
                quote=s["quote"],
            )
            for s in old["positive_content_spans"]
        ],
        positive_actions=[dict(action_id=a) for a in old["positive_action_ids"]],
    )
    ref = dict(path="synthetic-authority", id="cpu-authority", sha256="a" * 64)
    manifest = encoding.supervision_manifest(
        episode,
        slot_id=old["slot_id"],
        authority_record=ref,
        projection=projection,
        population_id="cpu-population",
        projection_authority="V12_A_original",
    )
    return episode, old, projection, manifest


def test_disjoint_original_targets_history_eos_and_L_P_unchanged(tokenizer):
    episode, old, _, manifest = inputs()
    before = old_encode(episode, old, tokenizer)
    after = encoding.encode_for_student(episode, manifest, tokenizer)
    assert after["rows"] == before["rows"]
    assert after["L_P"] == before["L_P"] == sum(after["layer_target_counts"].values())
    assert after["state_independent"] and not after["state_or_chi_used"]
    assert not after["training_authorized"] and after["not_a_TokenReceipt"]
    assert after["original_history_retained"] and after["context_limit"] == 24576


def test_boolean_union_is_after_individual_token_boundaries_not_character_merge():
    offsets = [(0, 4), (4, 8), (8, 10), (10, 14)]
    spans = [(4, 6), (5, 10), (5, 10)]
    assert encoding.token_position_union(offsets, spans, prompt_token_count=1) == [2]
    assert encoding.token_position_union(offsets, [(4, 10)], prompt_token_count=1) == [1, 2]


def test_same_authority_overlap_retained_but_no_duplicate_token_or_loss(tokenizer):
    episode, _, projection, manifest = inputs()
    baseline = encoding.encode_for_student(episode, manifest, tokenizer)
    projection["positive_content"] += copy.deepcopy(projection["positive_content"])
    overlapping = encoding.supervision_manifest(
        episode,
        slot_id=manifest["slot_id"],
        authority_record=manifest["authority_record"],
        projection=projection,
        population_id=manifest["population_id"],
        projection_authority="V14_derived_overlap",
    )
    value = encoding.encode_for_student(episode, overlapping, tokenizer)
    assert len(overlapping["positive_content_spans"]) == 2 * len(manifest["positive_content_spans"])
    assert value["L_P"] == baseline["L_P"]
    assert [r["target_positions"] for r in value["rows"]] == [
        r["target_positions"] for r in baseline["rows"]
    ]
    assert all(len(r["target_positions"]) == len(set(r["target_positions"])) for r in value["rows"])


def test_real_crossing_token_not_added_by_overlapping_character_envelopes(tokenizer):
    episode, _, projection, manifest = inputs()
    full = encoding.encode_for_student(episode, manifest, tokenizer)
    row = full["rows"][0]
    offsets = tokenizer(
        row["rendered_prompt"] + row["rendered_response"],
        add_special_tokens=False,
        truncation=False,
        return_offsets_mapping=True,
    )["offset_mapping"]
    prompt_len = len(row["rendered_prompt"])
    target, (a, b) = next(
        (i, (a - prompt_len, b - prompt_len))
        for i, (a, b) in enumerate(offsets)
        if a >= prompt_len and b <= prompt_len + len(episode.turns[0].raw_text) and b - a >= 3
    )
    doc = projection["positive_content"][0]["segment_id"]
    text = episode.turns[0].raw_text
    projection["positive_content"] = [
        dict(segment_id=doc, start=a, end=a + 2, quote=text[a : a + 2]),
        dict(segment_id=doc, start=a + 1, end=b, quote=text[a + 1 : b]),
    ]
    narrowed = encoding.supervision_manifest(
        episode,
        slot_id=manifest["slot_id"],
        authority_record=manifest["authority_record"],
        projection=projection,
        population_id=manifest["population_id"],
        projection_authority="V14_derived_overlap",
    )
    value = encoding.encode_for_student(episode, narrowed, tokenizer)
    assert target not in value["rows"][0]["layer_target_positions"]["reason"]
    assert target in encoding.token_position_union(
        offsets, [(prompt_len + a, prompt_len + b)], prompt_token_count=row["prompt_token_count"]
    )


def test_authority_changes_cache_key_and_forged_masks_are_rejected(tokenizer):
    episode, _, _, manifest = inputs()
    registration = dict(
        tokenizer_binding=list(tokenizer_binding(tokenizer)),
        encoding_source_bindings={"cpu": "frozen"},
        tokenizer_runtime={},
    )
    original = dict(episode_sha256=digest(episode), sha256="b" * 64)
    changed = copy.deepcopy(manifest)
    changed["authority_record"]["sha256"] = "c" * 64
    changed["id"] = digest({k: v for k, v in changed.items() if k != "id"})
    assert cache._cache_key(registration, original, manifest) != cache._cache_key(
        registration, original, changed
    )
    forged = copy.deepcopy(manifest)
    forged["positive_content_spans"] = []
    forged["id"] = digest({k: v for k, v in forged.items() if k != "id"})
    with pytest.raises(ValueError, match="exact original authority"):
        encoding.encode_for_student(episode, forged, tokenizer)
    with pytest.raises(ValueError, match="24576"):
        encoding.encode_for_student(episode, manifest, tokenizer, context_limit=2048)


def test_append_cache_encodes_before_mapping_and_never_reencodes_existing_keys(
    tmp_path, monkeypatch, tokenizer
):
    episode, _, projection, _ = inputs()
    raw = episode.model_dump_json().encode()
    episode_path = tmp_path / "original.json"
    episode_path.write_bytes(raw)
    original = dict(
        path=str(episode_path),
        sha256=hashlib.sha256(raw).hexdigest(),
        episode_sha256=digest(episode),
    )
    slots, pairs, projections = ["s0", "s1", "s2"], [], {}
    for sid in slots:
        view = public_trajectory_view(episode, slot_id=sid)
        local_projection = copy.deepcopy(projection)
        for span in local_projection["positive_content"]:
            span["segment_id"] = view["turns"][0]["public_content_segment_id"]
        local_projection["positive_actions"] = [
            dict(action_id=a["action_id"]) for a in view["turns"][0]["actions"]
        ]
        projections[sid] = local_projection
        record = bound(
            dict(
                schema="synthetic_V12_paid_A",
                actual_model_call_receipt_verified=True,
                new_pipeline_outcomes=dict(projection_usable=True),
                inspection=dict(auxiliary=dict(supervision=local_projection)),
                request=dict(candidate_request=dict(trajectory=view)),
            )
        )
        persist(tmp_path / "source" / sid, record)
        pairs.append(
            dict(
                slot_id=sid,
                task_id=episode.task_id,
                original_episode=original,
                A_record=cache.entry(tmp_path / "source" / sid / "record.json"),
            )
        )
    persist(tmp_path / "assets", bound(dict(assets={})))
    registration = bound(
        dict(
            schema=cache.REGISTRATION_SCHEMA,
            population_id="cpu-population",
            candidate_slot_ids=slots,
            original_student_assets=cache.entry(tmp_path / "assets/record.json"),
            tokenizer_binding=list(tokenizer_binding(tokenizer)),
            encoding_source_bindings={"synthetic": "frozen"},
            tokenizer_runtime={},
        )
    )
    definition = dict(pairs=pairs, tasks=[dict(task_id=episode.task_id, slot_ids=slots)])
    monkeypatch.setattr(cache, "_registration", lambda _: (registration, definition))
    monkeypatch.setattr(cache, "load_tokenizer", lambda _: tokenizer)
    added = [
        cache._authority_entry(tmp_path, registration, p, p["A_record"], "V12_A_original")
        for p in pairs[:2]
    ]
    revision = bound(
        dict(
            schema=cache.REVISION_SCHEMA,
            registration_id=registration["id"],
            index=0,
            previous_revision=None,
            added_authorities=added,
            known_authority_count=2,
            pending_slot_ids=["s2"],
        )
    )
    persist(tmp_path / "revisions/0000", revision)
    first = cache.run(tmp_path, workers=1)
    previous = {sid: Path(ref["path"]).read_bytes() for sid, ref in first["encoding_refs"].items()}
    loaded = cache.load_cache(tmp_path)
    assert loaded["slot_ids"] == slots and loaded["pending_slot_ids"] == ["s2"]
    assert loaded["known_encoded_count"] == 2 and not loaded["training_authorized"]
    assert loaded["full_population_layer_target_counts"] is None
    with pytest.raises(ValueError, match="2468"):
        cache.load_cache(tmp_path, require_complete=True)
    view = public_trajectory_view(episode, slot_id="s2")
    new = bound(
        dict(
            schema="v14_paid_material_annotation.v1",
            actual_model_call_receipt_verified=True,
            inspection=dict(usable=True, projection=projections["s2"]),
            request=dict(views=[view], purpose="projection"),
        )
    )
    persist(tmp_path / "new_authority", new)
    ref = cache.entry(tmp_path / "new_authority/record.json")
    cache.append_authorities(
        tmp_path,
        [dict(slot_id="s2", projection_authority="V14_completion_only", authority_record=ref)],
    )
    second = cache.run(tmp_path, workers=1)
    assert set(second["encoding_refs"]) == set(slots)
    assert all(
        Path(second["encoding_refs"][sid]["path"]).read_bytes() == raw
        for sid, raw in previous.items()
    )
    with pytest.raises(ValueError, match="pending"):
        cache.append_authorities(
            tmp_path,
            [dict(slot_id="s2", projection_authority="V14_completion_only", authority_record=ref)],
        )
    # A cache read never calls the tokenizer again, but source-byte mutation still blocks it.
    monkeypatch.setattr(
        cache, "load_tokenizer", lambda _: (_ for _ in ()).throw(AssertionError("retokenized"))
    )
    assert cache.load_cache(tmp_path)["known_encoded_count"] == 3
    episode_path.write_bytes(raw + b"\n")
    with pytest.raises(ValueError, match="episode bytes changed"):
        cache.load_cache(tmp_path)


def test_v14_consumer_dispatch_and_actual_step_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(v10_training, "read_json", lambda _: {"schema": "v14_material_binding.v1"})
    module_name = "trusted_synthesis.finance_research.v14_material"
    monkeypatch.setitem(
        sys.modules, module_name, SimpleNamespace(load_training_pool=lambda _: "V14_pool")
    )
    assert v10_training.load_training_pool("synthetic") == "V14_pool"
    run = cpu_driver(tmp_path / "cpu")
    run.pool.material_schema = "v14_material_binding.v1"
    result = run.step()
    assert result["schema_version"] == "v14_actual_task_batch_update.v1"
    assert result["supervision_policy"] == encoding.ENCODING_POLICY
    assert result["additional_batch_division"] is False
