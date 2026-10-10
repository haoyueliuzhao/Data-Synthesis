"""One separately authorized R0/R3 comparison; the original B queue stays paused.

Reuse the sealed V32 queue and numerical validators through a private module,
not a second training/replay implementation. Only protocol construction,
selection and the hard-coded worker path need local adapters. Import is CPU-only.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V25_SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
V32_ROOT = V25_SOURCE_ROOT / "replay_performance_01"
ROOT = V25_SOURCE_ROOT / "replay_performance_02"
FILES = (
    "finqa_v33_bounded_controller.py",
    "finqa_v33_performance_worker.py",
    "finqa_v33_activation_residency.py",
)
V32_IMPLEMENTATION_ID = "1d0e0645bd908d041bf01c94e83f14220aea1158e0f10e1e2d42d0b1c40cdb8a"
V32_PROTOCOL_ID = "abb414f05f29c6386042a309100f9dc4d47d3c360736de78ea8e3c497a6e858b"
V32_CLOSEOUT_ID = "04b6c8885911096a9a3f77161d69bde50e7d13a640bb296f5cfb66bea67e0c1b"
BACKEND_VERSION = "v33_r2_independent_nonkv_activation_residency.v1"
MICRO_STAGES = ("micro_R0", "micro_R3")
STAGES = (*MICRO_STAGES, "cohort_first", "cohort_resume")
STAGE_TIMEOUTS = {**{stage: 2 * 3600 for stage in STAGES}, "cohort_resume": 14 * 3600}
AUTHORIZATION_QUESTION = (
    "R2实测为1.120倍，未达到原1.20倍准入门槛。你希望另行登记一次针对同步与数据搬运的"
    "有界优化对照（原B仍暂停），还是仅封存结果、保持全部暂停？"
)
AUTHORIZATION_ANSWER = "另行登记一次有界优化对照"
AUTHORIZATION_SCOPE = "one R0/R3 zero-new-sampling contrast; original B remains paused"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _sealed_body(path, expected_id):
    body = json.loads(Path(path).read_bytes())
    identity = hashlib.sha256(
        json.dumps(
            {k: v for k, v in body.items() if k != "id"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    require(body.get("id") == expected_id == identity, "pinned V32 record changed")
    return body


def _load_v32(name, *, local):
    manifest = _sealed_body(V32_ROOT / "implementation/record.json", V32_IMPLEMENTATION_ID)
    directory = Path(__file__).resolve().parent if local else V32_ROOT / "implementation"
    path = directory / "finqa_v32_performance_controller.py"
    if local and not path.exists():
        path = V32_ROOT / "implementation/finqa_v32_performance_controller.py"
    require(
        hashlib.sha256(path.read_bytes()).hexdigest() == manifest["sha256"][path.name],
        "sealed V32 controller bytes changed",
    )
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Keep the common-protocol validator pristine. Runtime dependency bindings are
# isolated from normal imports of V32 and never change a sealed source file.
_common = _load_v32(__name__ + "_common", local=False)
_runtime = _load_v32(__name__ + "_runtime", local=True)
ALLOWED_GPUS = _common.ALLOWED_GPUS
MINIMUM_FREE_MIB = _common.MINIMUM_FREE_MIB
WAIT_BUDGET_SECONDS = _common.WAIT_BUDGET_SECONDS
TERM_GRACE_SECONDS = _common.TERM_GRACE_SECONDS
POLL_SECONDS = _common.POLL_SECONDS


def __getattr__(name):
    return getattr(_runtime, name)


checked = _common.checked
sha = _common.sha
digest = _common.digest
entry = _common.entry
read_ref = _common.read_ref
file_ref = _common.file_ref
publish = _common.publish
now = _common.now
status = _common.status
inventory = _common.inventory
eligible = _common.eligible
verify_original_B_paused = _common.verify_original_B_paused
worker_environment = _common.worker_environment
birth = _common.birth
signal_owned = _common.signal_owned
verify_durable_prefix = _common.verify_durable_prefix


def inherited_protocol():
    common = _common.checked_protocol(V32_ROOT)
    require(common["id"] == V32_PROTOCOL_ID, "different V32 common protocol")
    closeout = _sealed_body(V32_ROOT / "closeout_01/record.json", V32_CLOSEOUT_ID)
    require(
        closeout["protocol"] == entry(V32_ROOT / "protocol/record.json")
        and closeout["decision"] == "MICRO_NUMERIC_PASS_THROUGHPUT_GATE_NOT_MET"
        and closeout["controller_and_workers_exited"] is True
        and closeout["owned_GPU_workers"] == 0
        and closeout["full_cohort_started"] is False
        and closeout["original_B_resume_authorized"] is False,
        "new contrast requires the sealed no-admission V32 closeout",
    )
    selection = read_ref(closeout["selection"])
    require(selection["selected_variant"] is None, "V32 admission state changed")
    read_ref(closeout["original_profile"])
    return common


def authorization_body():
    return dict(
        schema="v33_explicit_followup_authorization.v1",
        user_date="2026-10-09",
        user_question=AUTHORIZATION_QUESTION,
        user_answer=AUTHORIZATION_ANSWER,
        authorization_scope=AUTHORIZATION_SCOPE,
        original_B_resume_authorized=False,
        original_audit_request=entry(V32_ROOT / "audit_request/record.json"),
        prior_closed_trial=entry(V32_ROOT / "closeout_01/record.json"),
    )


def _freeze(root, commit):
    """New code is committed; all ten inherited files retain sealed V32 bytes."""
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    require(len(commit) == 40, "full source commit required")
    original = _sealed_body(V32_ROOT / "implementation/record.json", V32_IMPLEMENTATION_ID)
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative),
            "source has uncommitted changes: " + name,
        )
        sources[name] = raw
    for name, expected in original["sha256"].items():
        raw = (V32_ROOT / "implementation" / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "frozen V32 dependency changed")
        sources[name] = raw
    destination = Path(root) / "implementation"
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    manifest = publish(
        destination / "record.json",
        dict(
            schema="v33_committed_bounded_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            inherited_V32_implementation=entry(V32_ROOT / "implementation/record.json"),
            inherited_V32_files=list(original["sha256"]),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )
    return commit, manifest


def protocol_body(common, implementation, root, *, at, observed):
    """All unchanged fields must exactly equal the sealed common contract."""
    body = copy.deepcopy({k: v for k, v in common.items() if k != "id"})
    body.pop("R2_minimum_extra_speedup")
    body.update(
        schema="v33_bounded_activation_residency_protocol.v1",
        at=at,
        source_commit=implementation["source_commit"],
        output_root=str(root),
        implementation_id=implementation["id"],
        inherited_common_protocol=entry(V32_ROOT / "protocol/record.json"),
        authorization=entry(root / "authorization/record.json"),
        previous_trial_closeout=entry(V32_ROOT / "closeout_01/record.json"),
        gpu_observation_at_registration=observed,
        micro_variants=["R0", "R3"],
        maximum_micro_response_calls=10,
        profile_case_id=None,
        profile_variant=None,
        profile_responses=0,
        previous_R0_profile=entry(V32_ROOT / "micro_R0/profile/record.json"),
        prior_profile_is_hypothesis_only=True,
        prior_timings_in_speed_ratio=False,
        paired_fresh_R0_baseline_required=True,
        candidate_count=1,
        candidate_variant="R3",
        candidate_base_variant="R2",
        candidate_change="bounded non-KV saved-activation GPU residency; unchanged replay math",
        resident_saved_activation_budget_bytes=16 * 1024**3,
        resident_activation_and_KV_budgets_independent=True,
        activation_budget_admission_rule=(
            "physical_free + max(reserved - allocated, 0) >= estimated_complete_KV_bytes "
            "+ resident_saved_KV_budget + resident_saved_activation_budget + free_reserve; "
            "physical_free >= free_reserve; unchanged V32 full/saved-KV admission"
        ),
        activation_budget_is_reservation=False,
        allocator_fragmentation_or_OOM_guarantee=False,
        stage_timeout_seconds=STAGE_TIMEOUTS,
        original_V32_protocol_or_results_may_be_modified=False,
    )
    body["replay_binding_expected"].update(
        backend_version=BACKEND_VERSION,
        adapter_source=file_ref(root / "implementation" / FILES[2]),
        inherited_V19_source=file_ref(root / "implementation/finqa_v19_optimized_replay.py"),
    )
    return body


def initialize(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    require(root == ROOT, "one registered V33 destination only")
    require(not root.exists(), "never overwrite or silently restart this contrast")
    common = inherited_protocol()
    observed = inventory()
    uuids = {str(row["index"]): row["uuid"] for row in observed if row["index"] in ALLOWED_GPUS}
    require(uuids == common["gpu_uuids"], "physical GPU identities changed since V32")
    _, implementation = _freeze(root, source_commit)
    publish(root / "authorization/record.json", authorization_body())
    protocol = publish(
        root / "protocol/record.json",
        protocol_body(
            common,
            implementation,
            root,
            at=now(),
            observed=observed,
        ),
    )
    status(
        root,
        dict(
            phase="REGISTERED_NOT_STARTED",
            protocol_id=protocol["id"],
            original_B_resume_authorized=False,
        ),
    )
    return protocol


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "fixed V33 destination required")
    common = inherited_protocol()
    protocol = checked(root / "protocol/record.json")
    implementation = checked(root / "implementation/record.json")
    original = _sealed_body(V32_ROOT / "implementation/record.json", V32_IMPLEMENTATION_ID)
    require(
        implementation["schema"] == "v33_committed_bounded_implementation.v1"
        and implementation["committed_files"] == list(FILES)
        and implementation["inherited_V32_implementation"]
        == entry(V32_ROOT / "implementation/record.json")
        and implementation["inherited_V32_files"] == list(original["sha256"])
        and set(implementation["sha256"]) == set(FILES) | set(original["sha256"])
        and len(implementation["source_commit"]) == 40,
        "V33 implementation binding changed",
    )
    for name, expected in implementation["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen source bytes changed")
        if name in original["sha256"]:
            require(expected == original["sha256"][name], "inherited source differs from V32")
    authorization = checked(root / "authorization/record.json")
    require(
        {k: v for k, v in authorization.items() if k != "id"} == authorization_body(),
        "explicit followup scope changed",
    )
    expected = protocol_body(
        common,
        implementation,
        root,
        at=protocol["at"],
        observed=protocol["gpu_observation_at_registration"],
    )
    require(
        {k: v for k, v in protocol.items() if k != "id"} == expected, "fixed V33 contract changed"
    )
    observed_uuids = {
        str(row["index"]): row["uuid"]
        for row in protocol["gpu_observation_at_registration"]
        if row["index"] in ALLOWED_GPUS
    }
    require(observed_uuids == common["gpu_uuids"], "registered GPU observation changed")
    verify_original_B_paused(protocol)
    return protocol


def check_replay_binding(protocol, binding, *, variant):
    require(
        variant == "R3" and binding["backend_identity"]["variant"] == "R3",
        "only preregistered R3 may enter cohort replay",
    )
    # V32 checks every point/reward/order/RNG/backend field but hard-codes R1/R2.
    # Normalize ONLY that enum in a copy; actual durable R3 identity stays intact.
    normalized = {**binding, "backend_identity": {**binding["backend_identity"], "variant": "R2"}}
    _runtime_original_binding(protocol, normalized, variant="R2")


def check_result(protocol, stage, result):
    require(stage in STAGES, "unregistered V33 stage")
    expected_variant = stage.removeprefix("micro_") if stage in MICRO_STAGES else "R3"
    require(result.get("active_variant") == expected_variant, "result candidate differs from stage")
    if stage in MICRO_STAGES:
        require(
            result["variant"] == expected_variant
            and result["warmup_responses"] == 1
            and result["profile_responses"] == 0
            and result["diagnostic_profile"] is None
            and result["case_count"] == len(protocol["cases"])
            and result["model_optimizer_rng_buffers_unchanged"] is True,
            "bounded response count/profile/state contract changed",
        )
    else:
        require(result["selected_variant"] == "R3", "cohort variant changed")
    return _runtime_original_result(protocol, stage, result)


def choose_variant(protocol, results):
    require(set(results) == set(MICRO_STAGES), "exactly one fresh R0/R3 pair required")
    for stage in MICRO_STAGES:
        check_result(protocol, stage, results[stage])
    times = {
        stage.removeprefix("micro_"): results[stage]["unprofiled_seconds"] for stage in MICRO_STAGES
    }
    selected = "R3" if times["R3"] <= times["R0"] / 1.20 else None
    return dict(
        selected_variant=selected,
        unprofiled_seconds=times,
        eligible_variants=["R3"] if selected else [],
        minimum_speedup=1.20,
        speedup_vs_paired_R0=times["R0"] / times["R3"],
        fresh_R0_baseline=True,
        prior_trial_timings_used=False,
        selection_is_not_formal_B_resume_authority=True,
    )


def worker_command(root, stage, row, protocol):
    command = _common.worker_command(root, stage, row, protocol)
    command[5] = str(Path(root) / "implementation" / FILES[1])
    return command


_runtime_original_binding = _runtime.check_replay_binding
_runtime_original_result = _runtime.check_result
for _name in (
    "STAGES",
    "MICRO_STAGES",
    "STAGE_TIMEOUTS",
    "BACKEND_VERSION",
    "checked_protocol",
    "check_result",
    "check_replay_binding",
    "choose_variant",
):
    setattr(_runtime, _name, globals()[_name])
# These lambdas keep the narrow adapters independently mockable in CPU tests.
_runtime.inventory = lambda: inventory()
_runtime.verify_original_B_paused = lambda protocol: verify_original_B_paused(protocol)


class Controller(_runtime.Controller):
    def __init__(self, root=ROOT):
        super().__init__(root)

    def run_stage(self, stage):
        """V32 stage lifecycle with the worker filename changed to the V33 shell."""
        require(self.active is None, "one worker including CPU initialization at a time")
        require(
            stage in STAGES and not (self.root / stage / "launch/record.json").exists(),
            "stage was already dispatched; automatic retry forbidden",
        )
        self.verify_original_B_paused()
        if stage == "cohort_resume":
            first = checked(self.root / "cohort_first/result/record.json")
            check_result(self.protocol, "cohort_first", first)
            verify_durable_prefix(self.protocol, first)
        row, lock = self.acquire_gpu(stage)
        process, launch = None, None
        try:
            self.verify_original_B_paused()
            worker = str(self.root / "implementation" / FILES[1])
            command = worker_command(self.root, stage, row, self.protocol)
            directory = self.root / stage
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / "worker.log").open("xb") as output:
                process = subprocess.Popen(
                    command,
                    cwd=REPO,
                    env=worker_environment(row),
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            born = birth(process.pid)
            require(born is not None, "worker exited before its ownership could be established")
            launch = dict(
                schema="v33_bounded_stage_launch.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                stage=stage,
                pid=process.pid,
                birth=born,
                worker=worker,
                command=command,
                gpu_index=row["index"],
                gpu_uuid=row["uuid"],
                gpu_observed=row,
                timeout_seconds=STAGE_TIMEOUTS[stage],
                term_grace_seconds=TERM_GRACE_SECONDS,
            )
            launch = publish(directory / "launch/record.json", launch)
            self.active = {
                key: launch[key] for key in ("stage", "pid", "birth", "gpu_index", "gpu_uuid")
            }
            self.update("RUNNING", stage=stage)
            deadline = time.monotonic() + STAGE_TIMEOUTS[stage]
            termination_at, timed_out = None, False
            while process.poll() is None:
                current = time.monotonic()
                if termination_at is None and (self.stop or current >= deadline):
                    timed_out = current >= deadline
                    signal_owned(launch, signal.SIGTERM)
                    termination_at = current
                    self.update("SAFE_BOUNDARY_STOP_REQUESTED", stage=stage, timed_out=timed_out)
                if termination_at is not None and current - termination_at >= TERM_GRACE_SECONDS:
                    signal_owned(launch, signal.SIGKILL)
                    process.wait(timeout=30)
                    break
                time.sleep(POLL_SECONDS)
            code = process.wait()
            publish(
                directory / "exit/record.json",
                dict(
                    schema="v33_bounded_stage_exit.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    stage=stage,
                    returncode=code,
                    timed_out=timed_out,
                    stop_requested=termination_at is not None,
                    no_retry=True,
                ),
            )
            require(
                termination_at is None and code == 0,
                "stage failed/stopped/timed out; no retry, fallback or further dispatch",
            )
            result = checked(directory / "result/record.json")
            check_result(self.protocol, stage, result)
            if stage == "cohort_first":
                verify_durable_prefix(self.protocol, result)
            elif stage == "cohort_resume":
                first = checked(self.root / "cohort_first/result/record.json")
                check_result(self.protocol, "cohort_first", first)
                verify_durable_prefix(self.protocol, first)
                require(
                    first["selected_variant"] == result["selected_variant"],
                    "cold resume changed selected backend",
                )
            return result
        except BaseException:
            if process is not None and launch is not None and process.poll() is None:
                signal_owned(launch, signal.SIGTERM)
                try:
                    process.wait(timeout=TERM_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    signal_owned(launch, signal.SIGKILL)
                    process.wait(timeout=30)
            raise
        finally:
            self.active = None
            lock.close()

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run only the frozen committed V33 controller",
        )
        return super().run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "run", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.action == "initialize":
        require(args.source_commit is not None, "committed source is required")
        result = initialize(args.root, source_commit=args.source_commit)
        print(json.dumps(dict(id=result["id"], status="REGISTERED_NOT_STARTED")))
    elif args.action == "run":
        Controller(args.root).run()
    else:
        result = checked_protocol(args.root)
        print(
            json.dumps(
                dict(
                    id=result["id"], gpu_observation=inventory(), original_B_resume_authorized=False
                )
            )
        )


if __name__ == "__main__":
    main()
