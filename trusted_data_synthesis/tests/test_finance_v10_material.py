"""Synthetic full-roster/real-tokenizer material controls; zero external calls."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_finance_research_r2 import TOKENIZER
from test_finance_v9_monetary_amendment import synthetic_parent as synthetic_parent
from test_finance_v10_budget import register
from test_finance_v10_budget import stopped_history as stopped_history
from test_finance_v10_budget import wallet as wallet
from test_finance_v10_review_production import paid, requests

from trusted_synthesis.finance_research import v10_material as material
from trusted_synthesis.finance_research import v10_review_protocol as review
from trusted_synthesis.finance_research import v10_training as training
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.storage import encode
from trusted_synthesis.finance_research.v10_budget import (
    BATCH_ID,
    generation_episode_id,
    map_episode_id,
)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(value))
    return material.entry(path)


def profile_inputs():
    tasks = ["t0", "t1"]
    joints = {"t0": ["p0", "p1"], "t1": ["p2"]}
    maps = {
        "t0": dict(
            mapping_status="complete",
            state_by_slot={"p0": "z0", "p1": "z1"},
            chi_by_state={"z0": 0, "z1": 1},
        ),
        "t1": dict(mapping_status="complete", state_by_slot={"p2": "z0"}, chi_by_state={"z0": 0}),
    }
    enc = {
        sid: dict(
            encoding_admitted=True,
            layer_target_counts=dict(reason=2, tool=1, final=1),
            public_content_present=True,
            public_content_without_positive_reason_targets=False,
            max_sequence_tokens=100,
            total_sequence_tokens=200,
            failures=[],
        )
        for sid in ("p0", "p1", "p2")
    }
    return tasks, joints, maps, enc


def test_no_minimum_N_singletons_retained_mu_and_dynamic_schedule():
    value = material.support_profile(*profile_inputs())
    assert value["N"] == 2 and value["mu"] == {"t0": "1/2", "t1": "1/2"}
    assert value["task_support"]["t1"]["joint_valid_slot_ids"] == ["p2"]
    assert value["exploratory_training_admitted"]
    assert value["execution_plan"]["final_step"] == 10
    assert value["execution_plan"]["feedback_denominator"] == 700
    assert value["capability_profile"]["D_pi"] == 1


def test_no_hard_joint_package_dropped_on_mapping_or_encoding_failure():
    tasks, joints, maps, enc = profile_inputs()
    maps["t0"] = dict(mapping_status="unknown")
    value = material.support_profile(tasks, joints, maps, enc)
    assert value["N"] == 2 and value["joint_valid_slot_ids"] == ["p0", "p1", "p2"]
    assert not value["material_complete"] and value["capability_profile"]["D_pi"] is None
    tasks, joints, maps, enc = profile_inputs()
    enc["p1"].update(encoding_admitted=False, failures=[{"reason": "untruncated_context_overflow"}])
    value = material.support_profile(tasks, joints, maps, enc)
    assert not value["material_complete"] and "p1" in value["joint_valid_slot_ids"]
    del enc["p1"]
    with pytest.raises(ValueError, match="all and only"):
        material.support_profile(tasks, joints, maps, enc)


def test_whole_reason_ablation_blocks_but_individual_zero_reason_is_not_a_quota():
    tasks, joints, maps, enc = profile_inputs()
    enc["p0"]["layer_target_counts"]["reason"] = 0
    enc["p0"]["public_content_without_positive_reason_targets"] = True
    value = material.support_profile(tasks, joints, maps, enc)
    assert value["exploratory_training_admitted"]
    assert value["capability_profile"]["public_content_all_masked_packages"] == ["p0"]
    for row in enc.values():
        row["layer_target_counts"]["reason"] = 0
    value = material.support_profile(tasks, joints, maps, enc)
    assert not value["material_complete"]
    assert any(
        b["reason"] == "all_public_reasoning_masked_supervision_projection"
        for b in value["capability_profile"]["blockers"]
    )


def test_degenerate_states_do_not_launch_five_nominally_different_conditions():
    tasks, joints, maps, enc = profile_inputs()
    maps["t0"]["chi_by_state"]["z1"] = 0
    value = material.support_profile(tasks, joints, maps, enc)
    assert value["material_complete"] and not value["exploratory_training_admitted"]


@pytest.fixture(scope="module")
def tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)


@pytest.fixture
def corpus(tmp_path, wallet, monkeypatch, tokenizer):
    # 1000/8000 are synthetic sealed metadata for this loader boundary test;
    # two originals, four reviews and one mapping use real temporary ledger transitions.
    root = tmp_path / "synthetic-new-v10"
    e0, pair0, raw0 = requests(0)
    e1, pair1, raw1 = requests(1, recovery=True)
    task = e0.task_id
    assert e1.task_id == task
    tasks = [task] + [f"unqualified-{i}" for i in range(999)]
    slots = [
        dict(
            task_id=t,
            slot_index=i,
            slot_id=generation_episode_id(BATCH_ID, t, i),
            purpose="common_material_candidate",
        )
        for t in tasks
        for i in range(8)
    ]
    register(wallet, generation_slots=slots)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    lineage = b"".join(
        (json.dumps(dict(original_id=t, source_group="synthetic-source")) + "\n").encode()
        for t in tasks
    )
    (snapshot / "lineage.jsonl").write_bytes(lineage)
    source = material.bound(
        dict(
            schema="synthetic_source",
            files={
                "lineage.jsonl": dict(
                    sha256=hashlib.sha256(lineage).hexdigest(), bytes=len(lineage)
                )
            },
        )
    )
    write(snapshot / "manifest.json", source)
    assets = material.bound(dict(assets={"synthetic_tokenizer": True}))
    asset_path = tmp_path / "assets/record.json"
    write(asset_path, assets)
    monkeypatch.setattr(material, "ORIGIN", asset_path)
    monkeypatch.setattr(material, "load_tokenizer", lambda _: tokenizer)
    original = material.bound(
        dict(
            schema="finqa_v7_new_full_probe.v1",
            task_ids=tasks,
            configs_by_task={t: e0.config.model_dump(mode="json") for t in tasks},
            snapshot_id=source["id"],
            prior_original_protocol_id=assets["id"],
        )
    )
    plan = material.bound(
        dict(
            schema="v10_new8000_generation_protocol.v1",
            original=original,
            task_ids=tasks,
            slots=slots,
            configs_by_task=original["configs_by_task"],
            batch_id=BATCH_ID,
            policy=review.review_policy_definition(),
            review_policy_id=review.review_policy_definition()["id"],
            api_model="deepseek-flash",
            budget_database=str(wallet.path),
            budget_config_sha256=digest(wallet.config),
            snapshot_id=source["id"],
            snapshot=str(snapshot),
        )
    )
    write(root / "registration/protocol.json", plan)
    outcomes, native_rows = [], []
    for index, slot in enumerate(slots):
        body = dict(
            schema="v10_generation_slot_outcome.v1",
            protocol_id=plan["id"],
            slot=slot,
            status="COMPLETE",
        )
        if index < 2:
            episode, request = (e0, pair0[0]) if index == 0 else (e1, pair1[0])
            path = root / "slots" / slot["slot_id"].split(":")[1] / "episode/episode.json"
            write(path, episode.model_dump(mode="json"))
            integrity = material.bound(
                dict(
                    schema="v10_generated_record_integrity.v1",
                    episode_sha256=digest(episode),
                    slot_id=slot["slot_id"],
                    checks=request["candidate_request"]["integrity"],
                )
            )
            integrity_path = path.parent.parent / "integrity/record.json"
            write(integrity_path, integrity)
            body.update(
                episode_path=str(path),
                episode_sha256=digest(episode),
                episode_file_sha256=material.sha(path),
                integrity_path=str(integrity_path),
                integrity_id=integrity["id"],
            )
            native_score = request["candidate_request"]["native_result"]
        else:
            native_score = {"native": {"execution_accuracy": 0.0, "program_accuracy": 0.0}}
        outcome = material.bound(body)
        outcomes.append(outcome)
        native_rows.append(
            dict(
                slot=slot,
                native=native_score,
                Q_native=index < 2,
                generation_outcome_id=outcome["id"],
            )
        )
    generation = material.bound(
        dict(
            schema="v10_whole_generation_seal.v1",
            protocol_id=plan["id"],
            batch_id=BATCH_ID,
            denominator=8000,
            all_slots_have_real_terminal=True,
            slots=outcomes,
        )
    )
    write(root / "generation_seal/record.json", generation)
    native = material.bound(
        dict(
            schema="v10_new_native_support.v1",
            protocol_id=plan["id"],
            batch_id=BATCH_ID,
            generation_seal_id=generation["id"],
            slot_denominator=8000,
            task_denominator=1000,
            M=2,
            rows=native_rows,
        )
    )
    write(root / "native_support/record.json", native)
    terminal, joint_records, joints = [], {}, []
    for pair, raw in ((pair0, raw0), (pair1, raw1)):
        records = []
        for request in pair:
            response = raw if request["role"] == "A" else {"process": raw["process"]}
            artifact, row, _ = paid(wallet, request, response)
            record = review.review_record(request, artifact, row)
            directory = root / "reviews" / request["slot_id"].split(":")[1] / request["role"]
            write(directory / "request/record.json", request)
            ref = write(directory / "record/record.json", record)
            terminal.append(
                dict(
                    slot_id=request["slot_id"],
                    role=request["role"],
                    episode_id=request["episode_id"],
                    terminal_kind="paid_model_return",
                    record=ref,
                )
            )
            records.append(record)
        joint = review.resolve_joint_review(*records, q_native=True)
        joints.append(joint)
        joint_records[joint["slot_id"]] = write(
            root / "joint" / joint["slot_id"].split(":")[1] / "record.json", joint
        )
    joint_ids = [j["slot_id"] for j in joints]
    seal = material.bound(
        dict(
            schema="v10_complete_process_review_seal.v1",
            protocol_id=plan["id"],
            batch_id=BATCH_ID,
            generation_seal_id=generation["id"],
            native_support_id=native["id"],
            M=2,
            expected_reviews=4,
            terminals=terminal,
            returned=4,
            network_unknowns=0,
            all_registered_jobs_terminal=True,
            joint_records=joint_records,
            joint_slot_ids=joint_ids,
            joint_by_task={task: joint_ids},
            N=1,
        )
    )
    write(root / "review_seal/record.json", seal)
    request = review.prepare_mapping_request(
        task_id=task, joint_records=joints, protocol_id=BATCH_ID
    )
    states = []
    for index, package in enumerate(request["packages"]):
        view = package["trajectory"]
        doc = next(
            d
            for d in view["segments"]
            if d["segment_id"] == view["turns"][-1]["public_content_segment_id"]
        )
        loc = dict(segment_id=doc["segment_id"], start=0, end=len(doc["text"]), quote=doc["text"])
        interventions = []
        if index:
            action = view["turns"][0]["actions"][0]
            event = next(e for e in view["events"] if e["event_id"] == action["event_id"])
            interventions.append(
                dict(
                    slot_id=package["slot_id"],
                    kind="revision",
                    action_id=action["action_id"],
                    observation_segment_id=event["observation_segment_id"],
                    consequence=loc,
                    effect="Expressed recovery after the actual zero-divisor error.",
                )
            )
        states.append(
            dict(
                state_id=f"z{index}",
                slot_ids=[package["slot_id"]],
                semantic_summary="Direct derivation"
                if not index
                else "Error-driven revised derivation",
                evidence=[dict(slot_id=package["slot_id"], **loc)],
                chi=index,
                chi_reason="Observed process consequence.",
                interventions=interventions,
            )
        )
    artifact, row, _ = paid(
        wallet, request, dict(mapping_status="complete", states=states, ambiguities=[])
    )
    mapped = review.mapping_record(request, artifact, row)
    directory = root / "mapping" / digest(task)
    write(directory / "request/record.json", request)
    map_ref = write(directory / "record/record.json", mapped)
    mapping = material.bound(
        dict(
            schema="v10_complete_task_mapping_seal.v1",
            protocol_id=plan["id"],
            batch_id=BATCH_ID,
            review_seal_id=seal["id"],
            expected_tasks=1,
            terminals=[
                dict(
                    task_id=task,
                    episode_id=map_episode_id(BATCH_ID, task),
                    terminal_kind="paid_model_return",
                    record=map_ref,
                )
            ],
            all_registered_jobs_terminal=True,
            all_joint_states_resolved=True,
        )
    )
    write(root / "mapping_seal/record.json", mapping)
    return root, plan, seal, wallet


def test_real_receipt_A_mask_once_mapping_binding_loads_new_consumer(corpus):
    root, plan, seal, ledger = corpus
    before = ledger.snapshot()
    result = material.freeze_material(root, plan, seal)
    assert result["training_admitted"] and result["N"] == 1
    pool = training.load_training_pool(result["binding"]["path"])
    assert pool.production_verified and pool.conditional_scope_verified
    assert pool.material_schema == material.BINDING_SCHEMA
    assert pool._manifest.registration.validator_binding_id.startswith("v10_")
    assert pool._manifest.registration.mu == {pool.task_ids[0]: "1"}
    assert set(pool._manifest.registration.pi0[pool.task_ids[0]].values()) == {"1/2"}
    assert set(pool.chi[pool.task_ids[0]].values()) == {0, 1}
    assert len(pool.packages) == 2 and pool.capability_profile["supervised_tokens"]["reason"] > 0
    assert (
        pool.execution_plan["final_step"] == 10
        and pool.execution_plan["feedback_denominator"] == 700
    )
    assert ledger.snapshot() == before


def test_partial_process_matrix_and_rehashed_paid_label_cannot_freeze(corpus):
    root, plan, seal, _ = corpus
    bad = copy.deepcopy(seal)
    bad["terminals"].pop()
    bad = material.bound({k: v for k, v in bad.items() if k != "id"})
    generation = material.read_json(root / "generation_seal/record.json")
    native = material.read_json(root / "native_support/record.json")
    mapping = material.read_json(root / "mapping_seal/record.json")
    with pytest.raises(ValueError):
        material.validate_complete_seals(plan, generation, native, bad, mapping)
    row = seal["terminals"][0]
    record = material.read_json(row["record"]["path"])
    record["process_validity"] = "unknown"
    record = material.bound({k: v for k, v in record.items() if k != "id"})
    row["record"] = write(row["record"]["path"], record)
    seal = material.bound({k: v for k, v in seal.items() if k != "id"})
    write(root / "review_seal/record.json", seal)
    mapping["review_seal_id"] = seal["id"]
    write(
        root / "mapping_seal/record.json",
        material.bound({k: v for k, v in mapping.items() if k != "id"}),
    )
    with pytest.raises(ValueError, match="replay"):
        material.freeze_material(root, plan, seal)
