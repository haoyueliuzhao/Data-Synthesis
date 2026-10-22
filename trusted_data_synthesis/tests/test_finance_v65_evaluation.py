"""CPU-only controls for the explicitly authorized five-branch generation."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v65_binding as binding
import finqa_v65_evaluation as evaluation


def rewrite(path, body):
    body = {key: value for key, value in body.items() if key != "id"}
    value = {**body, "id": binding.digest(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def generation_fixture(tmp_path, monkeypatch, *, exit_code=0, wrong_birth=False):
    root, science = tmp_path / "early_generation_01", tmp_path / "scientific"
    monkeypatch.setattr(binding, "ROOT", root)
    monkeypatch.setattr(binding, "SCIENTIFIC_ROOT", science)
    scientific = rewrite(science / "protocol/record.json", dict(
        evaluation=evaluation.original.evaluation_contract(),
        evaluation_source_registration=dict(path="/mock/public", sha256="a" * 64),
        old_evaluation_registration=dict(path="/mock/old", sha256="b" * 64)))
    eligible = {}
    for index, (seed, arm) in enumerate(evaluation.ELIGIBLE_COORDINATES):
        key = evaluation.original.stats.coordinate(seed, arm)
        stage = science / f"stages/seed{seed}/train_{arm}"
        attempt = stage / "attempts/attempt0001"
        branch_path = science / f"branches/seed{seed}/{arm}/completed/record.json"
        branch = rewrite(branch_path, dict(
            schema="v63_fixed_q_branch_complete.v1", protocol_id=scientific["id"],
            status="COMPLETE", seed=seed, arm=arm, feedback_batch=1,
            optimizer_updates=298, new_optimizer_updates=298,
            snapshots={"894": dict(path=f"/mock/{key}/894", state_sha256="s" * 64,
                                   record_sha256="r" * 64, actual_state_digest="d" * 64)}))
        jobid = f"seed{seed}.train_{arm}"
        rewrite(attempt / "launch/record.json", dict(protocol_id=scientific["id"],
            job=dict(job_id=jobid), pid=100 + index, birth="same-birth", attempt=1))
        rewrite(attempt / "actual_exit/record.json", dict(protocol_id=scientific["id"],
            job_id=jobid, pid=100 + index, birth="wrong" if wrong_birth else "same-birth",
            attempt=1, returncode=exit_code, actual_waitpid_observed=True))
        result = rewrite(stage / "result/record.json", dict(
            protocol_id=scientific["id"], status="COMPLETE", seed=seed, arm=arm, stage=f"train_{arm}",
            optimizer_updates=298, new_optimizer_updates=298, final_step=894,
            resources=dict(all_gates_passed=True), branch_result=binding.entry(branch_path)))
        rewrite(stage / "accepted/record.json", dict(protocol_id=scientific["id"], job_id=jobid,
            result=binding.file_ref(stage / "result/record.json"), result_id=result["id"],
            actual_exit=binding.file_ref(attempt / "actual_exit/record.json"),
            actual_exit_zero=True, resources_passed=True, attempt=1))
        eligible[key] = {name: binding.entry(path) for name, path in dict(
            branch=branch_path, result=stage / "result/record.json", accepted=stage / "accepted/record.json",
            actual_exit=attempt / "actual_exit/record.json", launch=attempt / "launch/record.json").items()}
    protocol = rewrite(root / "protocol/record.json", dict(
        evaluation=evaluation.evaluation_contract(), science_protocol_ref=binding.entry(
            science / "protocol/record.json"), eligible_training_branches=eligible))
    return SimpleNamespace(root=root, science=science, protocol=protocol, scientific=scientific)


def test_exact_twenty_original_jobs_and_no_scoring_api():
    expected = {key: value for key, value in evaluation.original.planned_jobs().items()
                if (value["seed"], value["arm"]) != (389, "C05")}
    assert evaluation.planned_jobs() == expected
    assert len(expected) == 20 and sum(job["denominator"] for job in expected.values()) == 6215
    contract = evaluation.evaluation_contract()
    assert contract["original_generation_jobs"] == 24 and contract["original_total_sessions"] == 7458
    assert contract["scoring_calls"] == 0 and not contract["private_scoring_authorized"]
    for forbidden in ("score", "seal_panel", "summary", "_score", "_old_summary", "_panel_private_bundles"):
        assert not hasattr(evaluation, forbidden)


def test_five_actual_exits_and_original_snapshots_are_required(tmp_path, monkeypatch):
    e = generation_fixture(tmp_path, monkeypatch)
    before = (e.science / "protocol/record.json").read_bytes()
    barrier = evaluation.generation_barrier(e.root)
    assert barrier["new_branches"] == barrier["snapshot_count"] == 5
    assert barrier["scientific_protocol_id"] == e.scientific["id"]
    assert barrier["original_six_branch_barrier_not_claimed_passed"]
    assert barrier["private_references_read"] is False
    assert (e.science / "protocol/record.json").read_bytes() == before
    assert all(key != "seed389/C05" for key in barrier["branches"])


@pytest.mark.parametrize("change", ["nonzero", "identity", "missing", "extra"])
def test_completion_booleans_cannot_replace_five_exact_exits(tmp_path, monkeypatch, change):
    e = generation_fixture(tmp_path, monkeypatch, exit_code=-9 if change == "nonzero" else 0,
                           wrong_birth=change == "identity")
    if change in ("missing", "extra"):
        body = deepcopy(e.protocol)
        if change == "missing":
            body["eligible_training_branches"].pop("seed137/C1")
        else:
            body["eligible_training_branches"]["seed389/C05"] = body["eligible_training_branches"]["seed137/C1"]
        rewrite(e.root / "protocol/record.json", body)
    with pytest.raises(ValueError, match="exactly five|actual successful exit"):
        evaluation.generation_barrier(e.root)
    assert not (e.root / "evaluations/training_barrier/record.json").exists()


class Identity:
    def __init__(self, **value):
        self.value = value

    @classmethod
    def model_validate(cls, value):
        return cls(**value)

    def model_dump(self, **kwargs):
        return self.value


def prepared_fixture(tmp_path, monkeypatch):
    e = generation_fixture(tmp_path, monkeypatch)
    cohorts = {role: dict(tasks=[f"{role}-{index}" for index in range(count)], denominator=count,
                          source_groups={}) for role, count in (("calibration", 120), ("development", 883))}
    source = dict(snapshot="same-public-snapshot", snapshot_id="same-snapshot-id", role_plan={"roles": "same"},
        assets=dict(base_binding=dict(id="same-base-model")),
        jobs={"original": dict(model_identity=dict(tokenizer_digest="same-tokenizer", chat_template_digest="same-chat"))})
    old = dict(snapshot=source["snapshot"], snapshot_id=source["snapshot_id"],
        role_plan=source["role_plan"], cohorts=cohorts, contract=evaluation.original.evaluation_contract())
    calls = []
    final = SimpleNamespace(ModelIdentity=Identity, parameter_digest=lambda values: "actual-parameter-digest",
        runtime_binding=lambda: {"frozen-native-provider": "same-hash"},
        prepare_run=lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(evaluation, "_runtime", lambda: final)
    monkeypatch.setattr(evaluation.original, "_public_source", lambda *_: (source, cohorts))
    monkeypatch.setattr(evaluation.original, "_old_registration", lambda *_: old)
    monkeypatch.setattr(evaluation.original, "_old_summary", lambda *_: pytest.fail("no old summary reads"))
    monkeypatch.setattr(evaluation.original, "_panel_private_bundles", lambda *_: pytest.fail("no private labels"))
    monkeypatch.setattr(evaluation, "_snapshot_state", lambda *_: {"parameters": "same actual saved parameters"})
    plan = evaluation.prepare_jobs(e.root)
    return e, plan, calls, final


def test_prepare_preserves_scientific_identity_and_public_generation_only(tmp_path, monkeypatch):
    e, plan, calls, _ = prepared_fixture(tmp_path, monkeypatch)
    assert len(calls) == 20
    assert evaluation.checked_plan(e.root) == plan
    assert plan["protocol_id"] == e.protocol["id"] != plan["scientific_protocol_id"] == e.scientific["id"]
    assert plan["scoring_calls"] == 0 and plan["private_references_read"] is False
    for job in plan["jobs"].values():
        expected = "v63-b1-evaluation:" + binding.digest(dict(protocol_id=e.scientific["id"],
            seed=job["seed"], arm=job["arm"], feedback_batch=1, step=894, checkpoint=job["checkpoint"]))
        assert job["model_identity"]["point_id"] == expected
    assert all(Path(args[2]).is_relative_to(e.root / "evaluations/jobs") for args, _ in calls)


@pytest.mark.parametrize("field", ["point_id", "config", "blocked_branch"])
def test_registered_plan_rejects_scientific_identity_or_dose_drift(tmp_path, monkeypatch, field):
    e, plan, _, _ = prepared_fixture(tmp_path, monkeypatch)
    changed = deepcopy(plan)
    job = next(iter(changed["jobs"].values()))
    if field == "point_id":
        job["model_identity"]["point_id"] = "v65:incorrect-identity"
    elif field == "config":
        job["config"]["max_new_tokens"] = 1024
    else:
        other = next(value for value in evaluation.original.planned_jobs().values()
                     if (value["seed"], value["arm"]) == (389, "C05"))
        changed["jobs"][other["job_id"]] = other
    rewrite(e.root / "evaluations/registration/record.json", changed)
    with pytest.raises(ValueError, match="dose|decoding|identity"):
        evaluation.checked_plan(e.root)


def test_source_root_and_panel_path_cannot_be_retargeted(tmp_path, monkeypatch):
    e = generation_fixture(tmp_path, monkeypatch)
    job = next(iter(evaluation.planned_jobs().values()))
    with pytest.raises(ValueError, match="independent root"):
        evaluation.job_root(e.science, job)
    with pytest.raises(ValueError, match="unregistered"):
        evaluation.generation_root(e.root, {**job, "panel": "../../outside"})
