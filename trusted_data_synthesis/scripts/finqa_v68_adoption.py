"""Read-only complete-model-group gates for separately authorized early scoring.

No private references, labels, providers, checkpoint tensors, generation calls,
or writes are reachable here. Four accepted original panel/draw jobs are one
indivisible eligibility unit; only the six original b1 groups may enter.
"""
from __future__ import annotations

from pathlib import Path

import finqa_v68_binding as b

SCHEMA = "v68_complete_original_model_group_eligibility.v1"
GIB = 1024 ** 3
require = b.require


def _sealing():
    return b.completion_module("finqa_v67_sealing")


def _read_at(reference, expected):
    require(Path(reference["path"]).resolve() == Path(expected).resolve(),
            "original generation evidence escaped its registered path")
    return b.read_ref(reference)


def _plans():
    sealing = _sealing()
    old_protocol, old_plan = sealing._checked_plan()
    evaluation = b.completion_module("finqa_v67_evaluation")
    new_protocol = b.checked(b.COMPLETION_ROOT / "protocol/record.json")
    new_plan = b.checked(b.COMPLETION_ROOT / "evaluations/registration/record.json")
    require(new_protocol["id"] == b.COMPLETION_PROTOCOL_ID
            and old_protocol["id"] == b.EARLY_PROTOCOL_ID
            and new_protocol["scientific_protocol_id"] == b.BASE_PROTOCOL_ID,
            "early scoring requires the exact original completion/scientific protocols")
    science = b.read_ref(new_protocol["science_protocol_ref"])
    require(science["id"] == b.BASE_PROTOCOL_ID
            and new_plan["schema"] == "v67_generation_only_registration.v1"
            and new_plan["protocol_id"] == new_protocol["id"]
            and new_plan["scientific_protocol_id"] == old_plan["scientific_protocol_id"] == b.BASE_PROTOCOL_ID
            and new_plan["feedback_batch"] == 1
            and new_plan["contract"] == evaluation.evaluation_contract()
            and new_plan["source_binding"] == evaluation._implementation_binding()
            and new_plan["runtime_binding"] == old_plan["runtime_binding"]
            and new_plan["original_evaluation_source"] == science["evaluation_source_registration"]
            and new_plan["old_evaluation_registration"] == science["old_evaluation_registration"]
            and new_plan["private_references_read"] is False and new_plan["scoring_calls"] == 0,
            "original final-generation registration or b1 identity changed")
    barrier = b.read_ref(new_plan["training_barrier"])
    require(barrier["protocol_id"] == new_protocol["id"]
            and barrier["scientific_protocol_id"] == b.BASE_PROTOCOL_ID
            and barrier["eligible_training_branches"] == new_protocol["eligible_training_branches"]
            and barrier["original_six_branch_barrier_passed"] is True,
            "final generation requires its original accepted training branch")
    planned = evaluation.original.planned_jobs()
    jobs = {**old_plan["jobs"], **new_plan["jobs"]}
    require(len(old_plan["jobs"]) == 20 and len(new_plan["jobs"]) == 4
            and not (set(old_plan["jobs"]) & set(new_plan["jobs"]))
            and set(jobs) == set(planned) and sum(job["denominator"] for job in jobs.values()) == 7458
            and all(all(jobs[key].get(field) == value for field, value in original.items())
                    for key, original in planned.items()),
            "only the original twenty plus four b1 jobs may be adopted; b0 and new draws are forbidden")
    for job in new_plan["jobs"].values():
        coordinate = f"seed{job['seed']}/{job['arm']}"
        require(job["checkpoint"] == barrier["snapshots"][coordinate + "/step894"]
                and job["model_identity"]["point_id"] == "v63-b1-evaluation:" + b.digest(dict(
                    protocol_id=b.BASE_PROTOCOL_ID, seed=job["seed"], arm=job["arm"], feedback_batch=1,
                    step=894, checkpoint=job["checkpoint"])), "original final model/checkpoint identity changed")
    return dict(old_protocol=old_protocol, old_plan=old_plan, new_protocol=new_protocol,
                new_plan=new_plan, jobs=jobs)


def _actual(reference, launch_reference, protocol_id, job_id, returncode, *, cpu=False):
    actual, launch = b.read_ref(reference), b.read_ref(launch_reference)
    require(actual["protocol_id"] == launch["protocol_id"] == protocol_id
            and actual["job_id"] == job_id
            and (launch.get("job_id") if cpu else launch["job"]["job_id"]) == job_id
            and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"])
            and actual["attempt"] == launch["attempt"]
            and actual["actual_waitpid_observed"] is True and actual["returncode"] == returncode
            and not _sealing()._same_live_identity(actual["pid"], actual["birth"]),
            "scoring requires the exact separately observed, exited generation/finalization process")
    if cpu:
        require(launch["cuda_visible_devices"] == "", "adopted envelope finalization must remain CPU-only")
    return actual, launch


def _adopted_result(key, job, sources):
    directory = b.COMPLETION_ROOT / "adopted" / key
    accepted_path = directory / "accepted/record.json"
    if not accepted_path.exists():
        return None
    accepted = b.checked(accepted_path)
    require(accepted["schema"] == "v67_composite_public_generation_acceptance.v1"
            and accepted["protocol_id"] == b.COMPLETION_PROTOCOL_ID
            and accepted["scientific_protocol_id"] == b.BASE_PROTOCOL_ID and accepted["job_id"] == key
            and accepted["original_generation_returncode"] == 1
            and accepted["original_failure_preserved"] is True
            and accepted["cpu_finalization_returncode"] == 0
            and accepted["cpu_finalization_actual_exit_zero"] is True
            and accepted["resources_passed"] is True
            and accepted["new_scientific_calls"] == accepted["scoring_calls"] == 0
            and accepted["private_references_read"] is False,
            "original exit one cannot be promoted to successful GPU generation")
    result = _read_at(accepted["result"], directory / "result/record.json")
    require(result["id"] == accepted["result_id"]
            and result["schema"] == "v67_cpu_finalized_generation_result.v1"
            and result["protocol_id"] == b.COMPLETION_PROTOCOL_ID
            and result["original_generation_returncode"] == 1 and result["original_failure_preserved"] is True
            and result["actual_new_response_calls"] == result["new_API_calls"] == 0,
            "read-only CPU adoption cannot regenerate or replace the original output")
    original = _sealing().eligible_source_job(b.COMPLETION_ROOT, key)
    require(original["status"] == "ELIGIBLE" and original["job"] == job
            and original["source_refs"] == result["source_refs"],
            "original known-TypeError, accepted resource lifetime or immutable source bytes changed")
    source_refs = result["source_refs"]
    require(accepted["original_generation_actual_exit"] == source_refs["actual_exit"],
            "original generation exit one evidence changed")
    cpu_attempt = b.COMPLETION_ROOT / "repairs" / key / "attempt0001"
    _read_at(accepted["cpu_finalization_actual_exit"], cpu_attempt / "actual_exit/record.json")
    cpu_launch_ref = b.entry(cpu_attempt / "launch/record.json")
    actual, _ = _actual(accepted["cpu_finalization_actual_exit"], cpu_launch_ref,
                        b.COMPLETION_PROTOCOL_ID, key, 0, cpu=True)
    closed = _read_at(result["cpu_resource_closeout"], cpu_attempt / "resource_closeout/record.json")
    resources = result["cpu_resources"]
    require(closed["status"] == "COMPLETE" and closed["pid"] == actual["pid"]
            and closed["resources"] == resources and resources["all_gates_passed"] is True
            and resources["CUDA_initialized"] is False and resources["received_signals"] == []
            and resources["peak_rss_bytes"] <= 64 * GIB
            and resources["minimum_host_available_bytes"] >= 96 * GIB
            and not (cpu_attempt / "failure/record.json").exists(),
            "original CPU finalization resources or stop disposition changed")
    return result, dict(accepted=b.entry(accepted_path), result=b.entry(directory / "result/record.json"),
        actual_exit=source_refs["actual_exit"], launch=source_refs["launch"],
        original_failure=source_refs["failure"], original_resource_closeout=source_refs["resource_closeout"],
        cpu_actual_exit=accepted["cpu_finalization_actual_exit"], cpu_launch=cpu_launch_ref,
        cpu_resource_closeout=result["cpu_resource_closeout"])


def _new_result(key, job, sources):
    directory = b.COMPLETION_ROOT / "evaluations/jobs" / key
    accepted_path = directory / "accepted/record.json"
    if not accepted_path.exists():
        return None
    accepted = b.checked(accepted_path)
    require(accepted["schema"] == "v63_actual_attempt_exit_and_result_accepted.v1"
            and accepted["protocol_id"] == b.COMPLETION_PROTOCOL_ID and accepted["job_id"] == key
            and accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True,
            "new generation requires accepted actual GPU exit zero")
    result = _read_at(accepted["result"], directory / "result/record.json")
    require(result["id"] == accepted["result_id"]
            and result["schema"] == "v67_generation_only_job_result.v1", "new generation result identity changed")
    attempt = directory / "attempts" / f"attempt{accepted['attempt']:04d}"
    _read_at(accepted["actual_exit"], attempt / "actual_exit/record.json")
    launch_ref = b.entry(attempt / "launch/record.json")
    actual, launch = _actual(accepted["actual_exit"], launch_ref, b.COMPLETION_PROTOCOL_ID, key, 0)
    require(all(launch["job"].get(field) == value for field, value in job.items()),
            "accepted generation launch model, checkpoint or decoding changed")
    resources = result["resources"]
    observations = Path(resources["observations_path"]).resolve()
    require(observations.is_relative_to(b.COMPLETION_ROOT / "resources" / key)
            and observations.name == "observations.jsonl", "generation resource evidence escaped its job")
    closed_path = observations.parent / "closeout/record.json"
    closed = b.checked(closed_path)
    require(closed["status"] == "COMPLETE" and closed["protocol_id"] == b.COMPLETION_PROTOCOL_ID
            and closed["job_id"] == key and closed["resources"] == resources
            and resources["all_gates_passed"] is True
            and resources["single_process_lifetime_includes_loading"] is True
            and resources.get("received_signals") == []
            and resources.get("observed_violation") is None
            and resources["peak_allocated_bytes"] <= 76 * GIB
            and resources["peak_rss_bytes"] <= 192 * GIB
            and resources["minimum_boundary_free_bytes"] >= 2 * GIB
            and resources["minimum_host_available_bytes"] >= 96 * GIB,
            "new generation original resource hard gates failed")
    require(closed["pid"] == actual["pid"] and closed["birth"] == actual["birth"]
            and closed["gpu_index"] == actual["gpu_index"],
            "the new generation resource lifetime must belong to its actual successful GPU process")
    return result, dict(accepted=b.entry(accepted_path), result=b.entry(directory / "result/record.json"),
        actual_exit=accepted["actual_exit"], launch=launch_ref, resource_closeout=b.entry(closed_path))


def _job_proof(key, sources):
    job = sources["jobs"][key]
    old = key in sources["old_plan"]["jobs"]
    source = b.SOURCE_GENERATION_ROOT if old else b.COMPLETION_ROOT
    plan = sources["old_plan"] if old else sources["new_plan"]
    found = _adopted_result(key, job, sources) if old else _new_result(key, job, sources)
    if found is None:
        return None
    result, refs = found
    directory = source / "evaluations/jobs" / key
    generation = directory / "shards" / job["panel"] / "generation"
    whole_path = (b.COMPLETION_ROOT / "adopted" / key if old else directory) / "whole_queue_seal/record.json"
    whole = _read_at(result["whole_queue_seal"], whole_path)
    native_path = generation / "generation_seal/seal.json"
    native = _read_at(whole["generation_seal"], native_path)
    run_path = generation / "run.json"
    run = b.checked(run_path)
    require(result["status"] == "COMPLETE" and result["job_id"] == key
            and result["registration_id"] == plan["id"]
            and result["scientific_protocol_id"] == b.BASE_PROTOCOL_ID
            and result["feedback_batch"] == 1 and result["sessions"] == job["denominator"]
            and result["scoring_calls"] == 0 and result["private_references_read"] is False
            and whole["id"] == result["whole_queue_seal_id"] and whole["job_id"] == key
            and whole["registration_id"] == plan["id"]
            and whole["scientific_protocol_id"] == b.BASE_PROTOCOL_ID
            and whole["feedback_batch"] == 1 and whole["checkpoint"] == job["checkpoint"]
            and whole["denominator"] == job["denominator"]
            and whole["generation_seal_id"] == native["id"] and whole["run_id"] == run["id"]
            and whole["all_provider_calls_settled"] is True
            and native["complete"] is True and native["all_provider_calls_settled"] is True
            and native["run_id"] == run["id"] and native["registered_denominator"] == job["denominator"]
            and len(native["episodes"]) == len(whole["episode_sha256"]) == job["denominator"]
            and run["config"] == job["config"] and run["provider"] == job["model_identity"]
            and run["tasks"] == plan["cohorts"][job["role"]]["tasks"]
            and run["runtime_binding"] == plan["runtime_binding"]
            and run["snapshot_id"] == plan["snapshot_id"] and run["role"] == job["role"],
            "all original model, panel/draw, b1 order and settled native generation identities must match")
    refs.update(plan=b.entry(source / "evaluations/registration/record.json"),
        protocol=b.entry(source / "protocol/record.json"), whole_queue_seal=b.entry(whole_path),
        native_seal=b.entry(native_path), run=b.entry(run_path))
    return dict(job_id=key, job=job, source_kind="V65_CPU_COMPOSITE" if old else "V67_GPU_EXIT_ZERO",
        generation_root=str(generation), job_root=str(directory), source_refs=refs,
        original_generation_returncode=1 if old else 0, private_references_read=False,
        canonical_episode_sha256=whole["episode_sha256"])


def _group(seed, arm, jobs):
    require(len(jobs) == 4 and sum(row["job"]["denominator"] for row in jobs.values()) == 1243
            and all(row["job"]["feedback_batch"] == 1 and row["job"]["step"] == 894
                    and (row["job"]["seed"], row["job"]["arm"]) == (seed, arm) for row in jobs.values()),
            "a complete model group needs exactly its four original b1 jobs")
    return dict(schema=SCHEMA, coordinate=f"seed{seed}/{arm}", seed=seed, arm=arm,
        scientific_protocol_id=b.BASE_PROTOCOL_ID, feedback_batch=1, step=894,
        job_ids=list(jobs), jobs=jobs, sessions=1243, all_four_jobs_accepted=True,
        global_24_job_barrier_not_claimed=True, private_references_read=False,
        new_generation_calls=0, scoring_calls=0)


def read_ready_groups(root=None, *, skip_coordinates=()):
    """Read cheap acceptance presence first; inspect complete pending groups only."""
    require(root is None or Path(root).resolve() == Path(b.ROOT).resolve(),
            "group discovery requires its independent scoring root")
    allowed = [f"seed{s}/{a}" for s, a in b.ELIGIBLE_COORDINATES]
    skip = set(skip_coordinates)
    require(skip <= set(allowed), "only already registered original groups may be skipped")
    planned = b.source_module("finqa_v63_evaluation").planned_jobs()
    sources = None
    ready, waiting = {}, {}
    for seed, arm in b.ELIGIBLE_COORDINATES:
        coordinate = f"seed{seed}/{arm}"
        if coordinate in skip:
            continue
        roster = [key for key, job in planned.items() if (job["seed"], job["arm"]) == (seed, arm)]
        require(len(roster) == 4, "each registered model coordinate has exactly four original jobs")
        missing = [key for key in roster if not ((b.COMPLETION_ROOT / "evaluations/jobs" / key
            if (seed, arm) == (389, "C05") else b.COMPLETION_ROOT / "adopted" / key)
            / "accepted/record.json").exists()]
        if missing:
            waiting[coordinate] = dict(status="WAIT", missing_job_ids=missing,
                                       complete_group_not_partially_scored=True)
            continue
        sources = sources or _plans()
        proofs = {key: _job_proof(key, sources) for key in roster}
        missing = [key for key, proof in proofs.items() if proof is None]
        if missing:
            waiting[coordinate] = dict(status="WAIT", missing_job_ids=missing,
                                       complete_group_not_partially_scored=True)
        else:
            ready[coordinate] = _group(seed, arm, proofs)
    return dict(schema="v68_read_only_complete_group_snapshot.v1", scientific_protocol_id=b.BASE_PROTOCOL_ID,
        ready_groups=ready, waiting_groups=waiting, allowed_coordinates=allowed,
        skipped_registered_coordinates=sorted(skip),
        private_references_read=False, generation_calls=0, scoring_calls=0, original_files_modified=False)


def validate_group_evidence(group, *, include_episodes=False):
    """Validate all four immutable public outputs before returning any for scoring."""
    coordinate = (group["seed"], group["arm"])
    require(coordinate in b.ELIGIBLE_COORDINATES and group["schema"] == SCHEMA,
            "partial scoring cannot expand beyond the explicitly frozen model groups")
    sources = _plans()
    roster = [key for key, job in sources["jobs"].items()
              if (job["seed"], job["arm"]) == coordinate]
    require(len(roster) == 4 and set(group["jobs"]) == set(group["job_ids"]) == set(roster),
            "partial group or replaced job cannot cross the scoring barrier")
    proofs = {key: _job_proof(key, sources) for key in roster}
    require(all(row is not None for row in proofs.values()), "not all four source jobs remain accepted")
    expected = _group(*coordinate, proofs)
    require({key: value for key, value in group.items() if key != "id"} == expected,
            "prepared complete-model eligibility or source references changed")
    sealing = _sealing()
    storage, native = sealing._native()
    validated = {}
    for key, proof in proofs.items():
        job = proof["job"]
        plan = b.read_ref(proof["source_refs"]["plan"])
        require(storage.runtime_binding() == plan["runtime_binding"], "original public runtime changed")
        progress = native.inspect_shard(proof["job_root"], dict(runtime_binding=plan["runtime_binding"],
            config=job["config"], model_identity=job["model_identity"], snapshot_id=plan["snapshot_id"]),
            dict(key=job["panel"], task_keys=plan["cohorts"][job["role"]]["tasks"]))
        require(progress == dict(completed=job["denominator"], denominator=job["denominator"], sealed=True),
                "native public validation requires every original complete episode")
        run, seal, episodes = storage.sealed_episodes(proof["generation_root"])
        require(run["id"] == proof["source_refs"]["run"]["id"]
                and seal["id"] == proof["source_refs"]["native_seal"]["id"]
                and [sealing.canonical_episode_hash(episode) for episode in episodes]
                    == proof["canonical_episode_sha256"], "canonical original Episode content changed")
        validated[key] = dict(run=run, seal=seal, episodes=episodes)
    return dict(group=group, native=validated) if include_episodes else group
