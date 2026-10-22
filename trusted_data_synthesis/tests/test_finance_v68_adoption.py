"""Public-only four-job admission; neither partial groups nor exit fiction pass."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v68_binding as b
import finqa_v68_adoption as adoption


def rewrite(path, body):
    body = {key: value for key, value in body.items() if key != "id"}
    value = dict(**body, id=b.digest(body))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


class Episode:
    def __init__(self, key):
        self.key = key

    def model_dump(self, *, mode):
        assert mode == "json"
        return dict(original_public_task=self.key, unchanged_answer="public generated content")


@pytest.fixture
def group_factory(tmp_path, monkeypatch):
    def create(*, new=False):
        root, old, completion = (tmp_path / name for name in ("scores", "old", "completion"))
        monkeypatch.setattr(b, "ROOT", root)
        monkeypatch.setattr(b, "SOURCE_GENERATION_ROOT", old)
        monkeypatch.setattr(b, "COMPLETION_ROOT", completion)
        monkeypatch.setattr(b, "BASE_PROTOCOL_ID", "science-id")
        monkeypatch.setattr(b, "ELIGIBLE_COORDINATES", tuple((s, a) for s in (137, 251, 389) for a in ("C1", "C05")))
        oldprotocol = rewrite(old / "protocol/record.json", dict(scientific_protocol_id="science-id", old=True))
        newprotocol = rewrite(completion / "protocol/record.json", dict(scientific_protocol_id="science-id", new=True))
        monkeypatch.setattr(b, "EARLY_PROTOCOL_ID", oldprotocol["id"])
        monkeypatch.setattr(b, "COMPLETION_PROTOCOL_ID", newprotocol["id"])
        planned = b.source_module("finqa_v63_evaluation").planned_jobs()
        jobs = {key: dict(job, checkpoint=dict(path=f"/unchanged/{job['seed']}/{job['arm']}", state_sha256="a"*64),
            model_identity=dict(point_id=f"original-b1-{job['seed']}-{job['arm']}")) for key, job in planned.items()}
        oldjobs = {key: job for key, job in jobs.items() if (job["seed"], job["arm"]) != (389, "C05")}
        newjobs = {key: job for key, job in jobs.items() if (job["seed"], job["arm"]) == (389, "C05")}
        cohorts = {role: dict(tasks=[f"{role}-{i}" for i in range(n)]) for role, n in (("calibration",120),("development",883))}
        shared = dict(scientific_protocol_id="science-id", snapshot_id="unchanged-public-snapshot",
            cohorts=cohorts, runtime_binding=dict(public="frozen"))
        oldplan = rewrite(old / "evaluations/registration/record.json", dict(shared, jobs=oldjobs))
        newplan = rewrite(completion / "evaluations/registration/record.json", dict(shared, jobs=newjobs))
        sources = dict(old_protocol=oldprotocol, old_plan=oldplan, new_protocol=newprotocol, new_plan=newplan, jobs=jobs)
        monkeypatch.setattr(adoption, "_plans", lambda: sources)
        coordinate = (389, "C05") if new else (137, "C1")
        chosen = {key: job for key, job in jobs.items() if (job["seed"], job["arm"]) == coordinate}
        source = completion if new else old
        plan = newplan if new else oldplan
        public = {}
        original_eligible = {}
        paths = {}
        for index, (key, job) in enumerate(chosen.items()):
            directory = source / "evaluations/jobs" / key
            gen = directory / "shards" / job["panel"] / "generation"
            pid, birth = 10000 + index, f"birth-{index}"
            attempt = directory / "attempts/attempt0001"
            protocol_id = newprotocol["id"] if new else oldprotocol["id"]
            rewrite(attempt / "launch/record.json", dict(protocol_id=protocol_id, job=job,
                attempt=1, pid=pid, birth=birth))
            rewrite(attempt / "actual_exit/record.json", dict(protocol_id=protocol_id, job_id=key,
                attempt=1, pid=pid, birth=birth, actual_waitpid_observed=True, returncode=0 if new else 1, gpu_index=index))
            resources = dict(all_gates_passed=True, single_process_lifetime_includes_loading=True,
                received_signals=[], observed_violation=None, peak_allocated_bytes=20*adoption.GIB,
                peak_rss_bytes=24*adoption.GIB, minimum_boundary_free_bytes=8*adoption.GIB,
                minimum_host_available_bytes=256*adoption.GIB,
                observations_path=str(source / f"resources/{key}/pid{pid}/observations.jsonl"))
            resource_path = source / f"resources/{key}/pid{pid}/closeout/record.json"
            rewrite(resource_path, dict(protocol_id=protocol_id, job_id=key, pid=pid, birth=birth,
                gpu_index=index, status="COMPLETE", resources=resources))
            run = rewrite(gen / "run.json", dict(config=job["config"], provider=job["model_identity"],
                role=job["role"], tasks=cohorts[job["role"]]["tasks"], runtime_binding=shared["runtime_binding"],
                snapshot_id=shared["snapshot_id"]))
            native = rewrite(gen / "generation_seal/seal.json", dict(complete=True, all_provider_calls_settled=True,
                run_id=run["id"], registered_denominator=job["denominator"], episodes=[{}]*job["denominator"]))
            episodes = [Episode(task) for task in run["tasks"]]
            public[str(gen)] = dict(run=run, seal=native, episodes=episodes)
            failurepath = attempt / "failure/record.json"
            if not new:
                rewrite(failurepath, dict(error="Object of type Episode is not JSON serializable", exact_original=True))
            originalrefs = dict(protocol=b.entry(source / "protocol/record.json"),
                plan=b.entry(source / "evaluations/registration/record.json"), launch=b.entry(attempt / "launch/record.json"),
                actual_exit=b.entry(attempt / "actual_exit/record.json"), resource_closeout=b.entry(resource_path),
                run=b.entry(gen / "run.json"), native_seal=b.entry(gen / "generation_seal/seal.json"))
            if not new:
                originalrefs["failure"] = b.entry(failurepath)
            target = directory if new else completion / "adopted" / key
            wholepath = target / "whole_queue_seal/record.json"
            whole = rewrite(wholepath, dict(job_id=key, registration_id=plan["id"], scientific_protocol_id="science-id",
                feedback_batch=1, checkpoint=job["checkpoint"], denominator=job["denominator"],
                generation_seal=b.entry(gen / "generation_seal/seal.json"), generation_seal_id=native["id"],
                run_id=run["id"], all_provider_calls_settled=True,
                episode_sha256=[b.digest(episode.model_dump(mode="json")) for episode in episodes]))
            resultbody = dict(schema="v67_generation_only_job_result.v1" if new else "v67_cpu_finalized_generation_result.v1",
                protocol_id=newprotocol["id"], registration_id=plan["id"], scientific_protocol_id="science-id",
                job_id=key, feedback_batch=1, sessions=job["denominator"], status="COMPLETE",
                whole_queue_seal=b.entry(wholepath), whole_queue_seal_id=whole["id"], scoring_calls=0,
                private_references_read=False, actual_new_response_calls=5 if new else 0, new_API_calls=0)
            if new:
                # The actual frozen V67 generation result has scientific identity,
                # but its control protocol is carried by accepted/launch/exit.
                resultbody.pop("protocol_id")
                resultbody["resources"] = resources
            else:
                cpudir = completion / "repairs" / key / "attempt0001"
                cpupid, cpubirth = pid+100, birth+"cpu"
                rewrite(cpudir / "launch/record.json", dict(protocol_id=newprotocol["id"], job_id=key,
                    attempt=1, pid=cpupid, birth=cpubirth, cuda_visible_devices=""))
                rewrite(cpudir / "actual_exit/record.json", dict(protocol_id=newprotocol["id"], job_id=key,
                    attempt=1, pid=cpupid, birth=cpubirth, actual_waitpid_observed=True, returncode=0))
                cpu = dict(all_gates_passed=True, CUDA_initialized=False, received_signals=[],
                    peak_rss_bytes=adoption.GIB, minimum_host_available_bytes=256*adoption.GIB)
                rewrite(cpudir / "resource_closeout/record.json", dict(status="COMPLETE", pid=cpupid, resources=cpu))
                resultbody.update(original_generation_returncode=1, original_failure_preserved=True,
                    source_refs=originalrefs, cpu_resources=cpu,
                    cpu_resource_closeout=b.entry(cpudir / "resource_closeout/record.json"))
                original_eligible[key] = dict(status="ELIGIBLE", job=job, source_refs=originalrefs)
            result = rewrite(target / "result/record.json", resultbody)
            if new:
                accept = dict(schema="v63_actual_attempt_exit_and_result_accepted.v1", protocol_id=newprotocol["id"],
                    job_id=key, attempt=1, result=b.entry(target / "result/record.json"), result_id=result["id"],
                    actual_exit=b.entry(attempt / "actual_exit/record.json"), actual_exit_zero=True, resources_passed=True)
            else:
                accept = dict(schema="v67_composite_public_generation_acceptance.v1", protocol_id=newprotocol["id"],
                    scientific_protocol_id="science-id", job_id=key, result=b.entry(target / "result/record.json"),
                    result_id=result["id"], original_generation_actual_exit=originalrefs["actual_exit"],
                    original_generation_returncode=1, original_failure_preserved=True,
                    cpu_finalization_actual_exit=b.entry(cpudir / "actual_exit/record.json"),
                    cpu_finalization_returncode=0, cpu_finalization_actual_exit_zero=True,
                    resources_passed=True, new_scientific_calls=0, scoring_calls=0, private_references_read=False)
            rewrite(target / "accepted/record.json", accept)
            paths[key] = dict(target=target, generation=gen, source_attempt=attempt, resource=resource_path,
                              cpu_attempt=None if new else cpudir)
        inspected = []
        def inspect(directory, metadata, shard):
            inspected.append(str(directory))
            return dict(completed=len(shard["task_keys"]), denominator=len(shard["task_keys"]), sealed=True)
        storage = SimpleNamespace(runtime_binding=lambda: shared["runtime_binding"],
            sealed_episodes=lambda path: tuple(public[str(path)][field] for field in ("run", "seal", "episodes")))
        native = SimpleNamespace(inspect_shard=inspect)
        fake = SimpleNamespace(_same_live_identity=lambda *_: False,
            eligible_source_job=lambda _, key: original_eligible[key],
            _native=lambda: (storage,native), canonical_episode_hash=lambda e:b.digest(e.model_dump(mode="json")))
        monkeypatch.setattr(adoption, "_sealing", lambda: fake)
        return SimpleNamespace(root=root, old=old, completion=completion, sources=sources, chosen=chosen,
            coordinate=f"seed{coordinate[0]}/{coordinate[1]}", paths=paths, inspected=inspected,
            public=public, fake=fake, native=native, new=new)
    return create


@pytest.mark.parametrize("new", [False, True])
def test_four_exact_jobs_require_real_accepted_exits_and_keep_original_outputs(group_factory,new):
    e=group_factory(new=new)
    before={str(path):path.read_bytes() for base in (e.old,e.completion) for path in base.rglob("*") if path.is_file()}
    found=adoption.read_ready_groups(e.root)
    assert list(found["ready_groups"])==[e.coordinate]
    assert len(found["waiting_groups"])==5
    assert not e.inspected, "discovery must not reread all Episode payloads each poll"
    group=found["ready_groups"][e.coordinate]
    assert group["sessions"]==1243 and len(group["jobs"])==4 and group["feedback_batch"]==1
    validated=adoption.validate_group_evidence(group,include_episodes=True)
    assert len(validated["native"])==4 and len(e.inspected)==4
    assert sum(len(row["episodes"]) for row in validated["native"].values())==1243
    assert {row["source_kind"] for row in group["jobs"].values()}=={"V67_GPU_EXIT_ZERO" if new else "V65_CPU_COMPOSITE"}
    assert before=={str(path):path.read_bytes() for base in (e.old,e.completion) for path in base.rglob("*") if path.is_file()}
    assert not e.root.exists()


def test_partial_model_group_waits_and_skips_deep_checks(group_factory,monkeypatch):
    e=group_factory()
    key=next(iter(e.paths))
    (e.paths[key]["target"] / "accepted/record.json").unlink()
    monkeypatch.setattr(adoption,"_plans",lambda:pytest.fail("no complete pending group needs plan reread"))
    found=adoption.read_ready_groups(e.root)
    assert not found["ready_groups"] and key in found["waiting_groups"][e.coordinate]["missing_job_ids"]
    assert not e.inspected


def test_already_registered_group_is_not_revalidated_per_poll(group_factory,monkeypatch):
    e=group_factory()
    monkeypatch.setattr(adoption,"_plans",lambda:pytest.fail("registered group must be skipped"))
    found=adoption.read_ready_groups(e.root,skip_coordinates=[e.coordinate])
    assert not found["ready_groups"] and e.coordinate not in found["waiting_groups"]
    assert found["skipped_registered_coordinates"]==[e.coordinate]


@pytest.mark.parametrize("new,field,value",[(False,"original_generation_returncode",0),
    (False,"cpu_finalization_returncode",1),(False,"original_failure_preserved",False),
    (False,"resources_passed",False),(True,"actual_exit_zero",False),(True,"resources_passed",False)])
def test_invalid_present_acceptance_is_hard_failure_not_wait(group_factory,new,field,value):
    e=group_factory(new=new)
    path=next(iter(e.paths.values()))["target"] / "accepted/record.json"
    body=b.checked(path);body[field]=value;rewrite(path,body)
    with pytest.raises(ValueError): adoption.read_ready_groups(e.root)


@pytest.mark.parametrize("new",[False,True])
def test_completed_boolean_does_not_replace_actual_waitpid(group_factory,new):
    e=group_factory(new=new)
    key=next(iter(e.paths));paths=e.paths[key]
    actual_path=(paths["source_attempt"] if new else paths["cpu_attempt"]) / "actual_exit/record.json"
    body=b.checked(actual_path);body["actual_waitpid_observed"]=False;rewrite(actual_path,body)
    accepted_path=paths["target"] / "accepted/record.json"
    accepted=b.checked(accepted_path)
    accepted["actual_exit" if new else "cpu_finalization_actual_exit"]=b.entry(actual_path)
    rewrite(accepted_path,accepted)
    with pytest.raises(ValueError): adoption.read_ready_groups(e.root)


def test_live_source_is_not_scoring_ready(group_factory):
    e=group_factory(new=True)
    e.fake._same_live_identity=lambda *_:True
    with pytest.raises(ValueError,match="exited generation"):
        adoption.read_ready_groups(e.root)


@pytest.mark.parametrize("field",["job_ids","feedback_batch","canonical"])
def test_registered_group_or_canonical_output_change_blocks_private_gate(group_factory,field):
    e=group_factory()
    group=adoption.read_ready_groups(e.root)["ready_groups"][e.coordinate]
    if field=="job_ids": group["job_ids"].pop()
    elif field=="feedback_batch": group["feedback_batch"]=0
    else:
        key=next(iter(e.public))
        e.public[key]["episodes"][0]=Episode("changed original answer")
    with pytest.raises(ValueError): adoption.validate_group_evidence(group,include_episodes=True)


def test_all_four_public_native_checks_precede_scoring_data_return(group_factory):
    e=group_factory()
    group=adoption.read_ready_groups(e.root)["ready_groups"][e.coordinate]
    calls=[]
    def inspector(*args):
        calls.append(1)
        if len(calls)==4:raise ValueError("last group job has unknown episode")
        count=len(args[2]["task_keys"])
        return dict(completed=count,denominator=count,sealed=True)
    e.native.inspect_shard=inspector
    with pytest.raises(ValueError,match="last group job"):
        adoption.validate_group_evidence(group,include_episodes=True)
    assert len(calls)==4
