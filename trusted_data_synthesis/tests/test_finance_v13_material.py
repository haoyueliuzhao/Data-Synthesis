"""V13 fixed-support and real CPU-consumer controls; no API or production training."""

import copy
from fractions import Fraction

import pytest
import torch
from test_finance_v9_conditional_training import TinyModel
from test_finance_v9_conditional_training import material as old_cpu_material
from test_finance_v10_process_review import fixture
from test_finance_v10_student_encoding import manifest as old_manifest
from test_finance_v10_student_encoding import tokenizer as tokenizer

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import optimizer_pullback
from trusted_synthesis.finance_research import v13_material as material_module
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.materials import TaskBatch, task_batch_examples
from trusted_synthesis.finance_research.v6_collection import bound
from trusted_synthesis.finance_research.v6_distribution import automatic_update, manual_distribution
from trusted_synthesis.finance_research.v6_task import public_trajectory_view
from trusted_synthesis.finance_research.v8_training_driver import VerifiedPool
from trusted_synthesis.finance_research.v9_conditional_training import (
    ConditionalTrainingDriver,
    build_task_schedule,
    execution_plan,
)
from trusted_synthesis.finance_research.v10_student_encoding import (
    encode_process_review_for_student as old_encode,
)
from trusted_synthesis.finance_research.v13_material import (
    BINDING_SCHEMA,
    supervision_manifest,
    support_profile,
)
from trusted_synthesis.finance_research.v13_student_encoding import (
    encode_for_student,
    validate_encoding,
)


def inputs():
    tasks = ["multi", "single"]
    slots = {"multi": ["p0", "p1"], "single": ["p2"]}
    maps = {
        "multi": dict(
            mapping_status="complete",
            deterministic_singleton=False,
            state_by_slot={"p0": "z0", "p1": "z1"},
            chi_by_state={"z0": 0, "z1": 1},
        ),
        "single": dict(
            mapping_status="complete",
            deterministic_singleton=True,
            state_by_slot={"p2": "only"},
            chi_by_state={"only": None},
            chi_status="not_required_for_weighting",
        ),
    }
    encodings = {
        s: dict(
            encoding_admitted=True,
            failures=[],
            layer_target_counts=dict(reason=2, tool=1, final=1),
            public_content_present=True,
            public_content_without_positive_reason_targets=False,
            max_sequence_tokens=100,
            total_sequence_tokens=100,
        )
        for s in ("p0", "p1", "p2")
    }
    return tasks, slots, maps, encodings


def test_fixed_support_keeps_true_singleton_without_fabricating_chi():
    result = support_profile(*inputs())
    assert result["material_complete"] and result["exploratory_training_admitted"]
    assert result["N"] == 2 and result["package_count"] == 3
    assert result["mu"] == {"multi": "1/2", "single": "1/2"}
    assert result["task_support"]["single"]["chi"] == {"only": None}
    dose = result["capability_profile"]["manual_intervention_dose"]["per_task"]["single"]
    assert dose["TV_plus"] == dose["TV_minus"] == "0"
    assert dose["chi_status"] == "not_required_for_weighting"


@pytest.mark.parametrize("fault", ["mapping", "projection", "encoding", "all_reason_zero"])
def test_any_failure_blocks_whole_pool_without_subset_or_denominator_change(fault):
    tasks, slots, maps, enc = inputs()
    projection = []
    if fault == "mapping":
        maps["multi"] = dict(mapping_status="unknown", state_by_slot={}, chi_by_state={})
    elif fault == "projection":
        projection = [dict(slot_id="p1", reason="projection_unresolved")]
    elif fault == "encoding":
        enc["p1"].update(
            encoding_admitted=False, failures=[dict(reason="untruncated_context_overflow")]
        )
    else:
        for value in enc.values():
            value["layer_target_counts"]["reason"] = 0
    result = support_profile(tasks, slots, maps, enc, projection_failures=projection)
    assert result["candidate_slot_ids"] == ["p0", "p1", "p2"]
    assert result["N"] == 2 and result["package_count"] == 3
    assert not result["material_complete"] and not result["exploratory_training_admitted"]


def test_zero_reason_single_package_is_reported_not_removed():
    tasks, slots, maps, enc = inputs()
    enc["p1"]["layer_target_counts"]["reason"] = 0
    enc["p1"]["public_content_without_positive_reason_targets"] = True
    result = support_profile(tasks, slots, maps, enc)
    assert result["material_complete"]
    assert result["capability_profile"]["public_content_all_masked_packages"] == ["p1"]


def test_null_chi_only_consumed_by_explicit_registered_singleton_branch():
    prior, chi = {"x": {"z": "1"}}, {"x": {"z": None}}
    with pytest.raises(ValueError, match="binary"):
        manual_distribution(prior, chi, direction="Manual+")
    for arm in ("Manual+", "Manual-"):
        assert (
            manual_distribution(prior, chi, direction=arm, registered_singleton_tasks=["x"])
            == prior
        )
    with pytest.raises(ValueError, match="singleton"):
        manual_distribution(
            {"x": {"a": "1/2", "b": "1/2"}},
            {"x": {"a": None, "b": None}},
            direction="Manual+",
            registered_singleton_tasks=["x"],
        )


def test_actual_singleton_centered_contribution_and_anchored_novelty_are_zero():
    pi, mu = {"x": {"z": "1"}}, {"x": "1"}
    gradients = {"x": {"z": {"w": torch.tensor([2.0, 3.0])}}}
    centered = optimizer_pullback.centered_contributions(
        gradients, pi, mu, {"w": torch.tensor([5.0, 7.0])}
    )
    assert centered["C"] == {"x": {"z": 0.0}}
    for arm in ("C-only", "Full"):
        update = automatic_update(pi, pi, centered["C"], mu, arm=arm)
        assert update["pi_next"] == {"x": {"z": 1.0}}
        assert update["task_diagnostics"]["x"]["N"] == {"z": 0.0}


def v13_cpu_material():
    old = old_cpu_material(7)
    packages = [p for p in old.packages if p["task_id"] != "q0" or p["package_id"] == "q0/s0"]
    chi = copy.deepcopy(old.chi)
    chi["q0"] = {"z0": None}
    pool = VerifiedPool(old.task_ids, packages, old._rows, binding_id="synthetic-v13-cpu", chi=chi)
    pool.material_schema = BINDING_SCHEMA
    pool.registered_singleton_tasks = ("q0",)
    return pool


def test_real_tail_batch_weights_have_no_extra_N_and_actual_manual_branch(tmp_path):
    pool = v13_cpu_material()
    prior = pool._manifest.registration.pi0
    batch = TaskBatch(
        task_ids=("q0", "q1"),
        sampling_probability={t: "1/7" for t in pool.task_ids},
        sampling_design="uniform_epoch_permutation",
        schedule_id="cpu",
        step=1,
    )
    examples = task_batch_examples(pool, prior, batch)
    assert {Fraction(p["target_token_coefficient"]) for p in examples if p["task_id"] == "q0"} == {
        Fraction(1, 4)
    }
    assert {Fraction(p["target_token_coefficient"]) for p in examples if p["task_id"] == "q1"} == {
        Fraction(1, 12)
    }

    def driver(path, arm):
        model = TinyModel()
        return ConditionalTrainingDriver(
            model, torch.optim.AdamW(model.parameters(), lr=1e-4), pool, root=path, seed=11, arm=arm
        )

    shared = driver(tmp_path / "shared", "shared")
    shared.run_until(shared.shared_step)
    for arm in ("Manual+", "Manual-"):
        run = driver(tmp_path / arm, arm)
        run.restore(shared.root / f"step{shared.shared_step:04d}_step", branch=True)
        assert run.pi["q0"] == {"z0": "1"}
        report = run.step()
        assert report["schema_version"] == "v13_actual_task_batch_update.v1"
        assert report["supervision_policy"] == "v13_fixed_authority_original_spans.v1"


def test_actual744_schedule_uses_tail_four_and_149_steps():
    plan = execution_plan(744)
    assert plan["steps_per_epoch"] == 149 and plan["tail_batch_size"] == 4
    assert plan["outer_steps"] == [298, 596, 894, 1192] and plan["final_step"] == 1490
    schedule = build_task_schedule([f"t{i}" for i in range(744)], 11)
    assert [len(b["task_ids"]) for b in schedule["batches"]].count(4) == 10


def test_v13_uses_identical_original_bytes_targets_eos_and_whole_package_denominator(tokenizer):
    import multiprocessing
    import os
    from pathlib import Path

    episode, request, body = fixture()
    original = old_manifest(request, body)
    projection = dict(
        usable=True,
        positive_content=[
            dict(
                segment_id=s["original_segment_id"],
                start=s["start"],
                end=s["end"],
                quote=s["quote"],
            )
            for s in original["positive_content_spans"]
        ],
        positive_actions=[dict(action_id=a) for a in original["positive_action_ids"]],
    )
    pair = dict(slot_id=original["slot_id"], projection_authority="V12_A_original")
    manifest = supervision_manifest(
        episode, pair, {"synthetic_cpu": True}, projection, protocol_id="cpu-v13"
    )
    old = old_encode(episode, original, tokenizer)
    new = encode_for_student(episode, manifest, tokenizer)
    assert new["rows"] == old["rows"]
    assert new["L_P"] == old["L_P"] == sum(new["layer_target_counts"].values())
    assert new["encoding_admitted"] and new["not_a_TokenReceipt"]
    assert new["schema"] == "v13_student_encoding.v1" and not new["training_authorized"]
    assert new == validate_encoding(new, episode, manifest, tokenizer)
    altered = copy.deepcopy(new)
    altered["rows"][0]["target_ids"].pop()
    with pytest.raises(ValueError, match="differs"):
        validate_encoding(altered, episode, manifest, tokenizer)
    assert manifest["projection_sha256"] == digest(projection)
    sid = manifest["slot_id"]
    parent_parallelism = os.environ.get("TOKENIZERS_PARALLELISM")
    with multiprocessing.get_context("fork").Pool(
        2,
        initializer=material_module._encoding_worker_init,
        initargs=(tokenizer, {sid: episode}, {sid: manifest}, Path("unused-cpu-output"), True),
    ) as workers:
        results = list(workers.imap(material_module._encode_registered_original, [sid, sid]))
    assert results == [new, new]
    assert os.environ.get("TOKENIZERS_PARALLELISM") == parent_parallelism


@pytest.mark.parametrize("unresolved", ["projection", "mapping"])
def test_collect_all_authority_barrier_does_not_load_tokenizer_or_encode_subset(
    tmp_path, monkeypatch, unresolved
):
    import hashlib

    episode, old_request, body = fixture()
    original = old_manifest(old_request, body)
    original_path = tmp_path / "original.json"
    raw = episode.model_dump_json().encode()
    original_path.write_bytes(raw)
    task, slots, records, pairs, views = episode.task_id, ["s0", "s1"], {}, [], {}

    def add(key, body):
        records[key] = bound(body)
        return {"path": key, "id": records[key]["id"]}

    projection = dict(
        usable=True,
        positive_content=[
            dict(
                segment_id=s["original_segment_id"],
                start=s["start"],
                end=s["end"],
                quote=s["quote"],
            )
            for s in original["positive_content_spans"]
        ],
        positive_actions=[dict(action_id=a) for a in original["positive_action_ids"]],
    )
    for sid in slots:
        view = public_trajectory_view(episode, slot_id=sid)
        views[sid] = view
        request = add(sid + "/request", dict(candidate_request={"trajectory": view}))
        a = add(
            sid + "/a",
            dict(
                actual_model_call_receipt_verified=True,
                request=records[request["path"]],
                new_pipeline_outcomes={"projection_usable": True},
                inspection={"auxiliary": {"supervision": projection}},
            ),
        )
        b = add(sid + "/b", dict(actual_model_call_receipt_verified=True))
        at, bt = add(sid + "/at", {"record": a}), add(sid + "/bt", {"record": b})
        missing = unresolved == "projection" and sid == "s1"
        core = add(
            sid + "/pair",
            dict(
                schema="v12_paired_process_core.v1",
                joint_process_candidate=True,
                slot_id=sid,
                task_id=task,
                A_terminal=at,
                B_terminal=bt,
                A_projection_usable=not missing,
            ),
        )
        pairs.append(
            dict(
                slot_id=sid,
                task_id=task,
                pair=core,
                A_record=a,
                B_record=b,
                A_request=request,
                projection_authority="V13_completion_only" if missing else "V12_A_original",
                original_episode=dict(
                    path=str(original_path),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    episode_sha256=digest(episode),
                ),
            )
        )
    original_plan = add(
        "original_plan",
        dict(
            configs_by_task={task: episode.config.model_dump(mode="json")},
            snapshot="synthetic",
            snapshot_id="snapshot",
        ),
    )
    prep = add("prep", dict(singletons=[]))
    definition = dict(
        id="population",
        inputs=dict(source_v10_plan=original_plan, source_v12_seal={"id": "seal"}),
        pairs=pairs,
    )
    plan = dict(protocol_identity="population", singleton_task_ids=[], preparation=prep)
    source = dict(
        v13_population_id="population",
        task_slot_ids=slots,
        source_review_seal={"id": "seal"},
        original_records=[
            {k: p[k] for k in ("slot_id", "pair", "A_record", "B_record", "A_request")}
            for p in pairs
        ],
    )
    mapping = (
        dict(mapping_status="unknown")
        if unresolved == "mapping"
        else dict(
            mapping_status="complete",
            deterministic_singleton=False,
            state_by_slot={"s0": "z0", "s1": "z1"},
            chi_by_state={"z0": 0, "z1": 1},
        )
    )
    annotations = {
        ("mapping", task): dict(
            request=dict(views=[views[s] for s in slots], source_bindings=source),
            record={"inspection": mapping},
        )
    }
    if unresolved == "projection":
        annotations["projection", "s1"] = dict(
            request=dict(views=[views["s1"]], source_bindings=source),
            record={"inspection": None},
            reference={"id": "unresolved"},
        )

    class MemoryReader:
        def read(self, ref):
            return records[ref["path"]]

    monkeypatch.setattr(
        material_module, "_population", lambda *_: (plan, definition, {task: slots})
    )
    monkeypatch.setattr(material_module, "_annotations", lambda *_: ({}, annotations))
    monkeypatch.setattr(material_module, "snapshot_manifest", lambda _: {"id": "snapshot"})

    def forbidden(_):
        raise AssertionError("partial material must not load the Student tokenizer")

    monkeypatch.setattr(material_module, "load_tokenizer", forbidden)
    result = material_module._collect(tmp_path, MemoryReader(), produce_encodings=True)
    assert result["tokenizer_binding"] is None
    assert set(result["encodings"]) == set(slots)
    assert not (tmp_path / "encoding").exists()
    assert not result["support"]["material_complete"]
    assert result["support"]["package_count"] == 2 and result["support"]["N"] == 1
    profile = result["support"]["capability_profile"]
    assert profile["supervised_tokens"] is None and profile["all_public_reasoning_masked"] is None
    assert profile["encoding_started_packages"] == 0
    assert not any(
        b["reason"] == "all_public_reasoning_masked_supervision_projection"
        for b in profile["blockers"]
    )
    if unresolved == "projection":
        assert profile["approved_public_content_characters"] is None
