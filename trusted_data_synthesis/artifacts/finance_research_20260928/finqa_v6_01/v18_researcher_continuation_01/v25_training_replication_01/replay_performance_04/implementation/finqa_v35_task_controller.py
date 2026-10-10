"""One bounded whole-task, four-GPU supplement; the original B stays paused.

Four disjoint static shards publish complete-task CPU gradient caches. Only
after all shard processes exit and every task validates may one GPU7 process
perform the global recomputation. The entire run shares one four-hour clock.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import shutil
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
V34_ROOT = V25_SOURCE_ROOT / "replay_performance_03"
ROOT = V25_SOURCE_ROOT / "replay_performance_04"
V34_IMPLEMENTATION_ID = "de4151bfaa4101940b333f83c0dcf51564fce7c3849f701a5cfb3827d9e9e0bf"
V34_PROTOCOL_ID = "480be5d26130d0b869afa11c5b33cfbd138bcf2ca4be269a5805229351de7a46"
V34_CLOSEOUT_ID = "e85e319a491a16833231cc881e8653bbdc93f74f0ef30683d695ad1acb1ce023"
AUDITED_COMMIT = "fbc23613fffd17fc56f7d242b27e00ad08eace8d"
AUDIT_ATTACHMENT = Path(
    "/home/zhuxinrui/.codex/attachments/c946eb5d-25f0-4234-936a-6964db9ea28c/已粘贴的文本.txt"
)
FILES = ("finqa_v35_task_controller.py", "finqa_v35_task_worker.py", "finqa_v35_task_cache.py")
ALLOWED_GPUS = (3, 4, 5, 7)
SHARD_STAGES = tuple(f"shard{index:02d}" for index in range(4))
STAGES = (*SHARD_STAGES, "coordinator")
STAGE_GPU = dict(zip(SHARD_STAGES, ALLOWED_GPUS, strict=True)) | {"coordinator": 7}
GLOBAL_DEADLINE_SECONDS = 4 * 3600
WAIT_BUDGET_SECONDS = 24 * 3600
TERM_GRACE_SECONDS = 10 * 60
POLL_SECONDS = 10
GIB = 1024**3
MINIMUM_FREE_MIB = 72 * 1024
MAXIMUM_ALLOCATED_BYTES = 76 * GIB
MINIMUM_DEVICE_FREE_BYTES = 2 * GIB
HOST_RAM = dict(
    shard_rss_limit_bytes=160 * GIB,
    coordinator_rss_limit_bytes=192 * GIB,
    reserve_bytes=96 * GIB,
    shard_admission_bytes=(4 * 160 + 96) * GIB,
    coordinator_admission_bytes=(192 + 96) * GIB,
    accounting="observed Linux MemAvailable and per-worker VmRSS/VmHWM; not a reservation",
    pinned_memory_is_in_RSS=True,
    independent_pinned_memory_hard_cap=False,
    finite_cgroup_ancestor_headroom_also_required=True,
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _sealed(path, expected_id):
    body = json.loads(Path(path).read_bytes())
    actual = hashlib.sha256(
        json.dumps(
            {k: v for k, v in body.items() if k != "id"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    require(body.get("id") == actual == expected_id, "pinned prior record changed")
    return body


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_prior_manifest = _sealed(V34_ROOT / "implementation/record.json", V34_IMPLEMENTATION_ID)
_prior_controller = V34_ROOT / "implementation/finqa_v34_tail_controller.py"
require(
    hashlib.sha256(_prior_controller.read_bytes()).hexdigest()
    == _prior_manifest["sha256"][_prior_controller.name],
    "prior controller bytes changed",
)
_common = _module(_prior_controller, __name__ + "_v34")
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
verify_original_B_paused = _common.verify_original_B_paused
worker_environment = _common.worker_environment
birth = _common.birth
signal_owned = _common.signal_owned
COHORT_COMPARISON_KEYS = _common.COHORT_COMPARISON_KEYS
BACKEND_VERSION = _common.BACKEND_VERSION
frozen_training_module = _common.frozen_training_module


def inherited_protocol():
    common = _common.checked_protocol(V34_ROOT)
    require(common["id"] == V34_PROTOCOL_ID, "wrong V34 source protocol")
    closeout = _sealed(V34_ROOT / "closeout_01/record.json", V34_CLOSEOUT_ID)
    queue = json.loads((V34_ROOT / "queue/status.json").read_bytes())
    require(
        queue["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and queue["protocol_id"] == V34_PROTOCOL_ID
        and queue["active_child"] is None,
        "V34 must remain stopped without retry",
    )
    require(
        closeout.get("original_B_resume_authorized") is False,
        "V34 closeout must preserve original B pause",
    )
    intent = checked(V34_ROOT / "queue/run_intent/record.json")
    launch = checked(V34_ROOT / "tail_validation/launch/record.json")
    require(
        all(birth(row["pid"]) != row["birth"] for row in (intent, launch)),
        "old V34 process still alive",
    )
    return common


def _freeze(root, commit):
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"],
        cwd=REPO,
        text=True,
    ).strip()
    require(len(commit) == 40, "full committed source required")
    original = _sealed(V34_ROOT / "implementation/record.json", V34_IMPLEMENTATION_ID)
    require(len(original["sha256"]) == 16, "exactly sixteen inherited V34 sources required")
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted source: " + name
        )
        sources[name] = raw
    for name, expected in original["sha256"].items():
        raw = (V34_ROOT / "implementation" / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "old frozen source changed")
        sources[name] = raw
    directory = Path(root) / "implementation"
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (directory / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return publish(
        directory / "record.json",
        dict(
            schema="v35_committed_task_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            inherited_V34_implementation=entry(V34_ROOT / "implementation/record.json"),
            inherited_V34_files=list(original["sha256"]),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )


def checked_implementation(root):
    implementation = checked(Path(root) / "implementation/record.json")
    original = _sealed(V34_ROOT / "implementation/record.json", V34_IMPLEMENTATION_ID)
    require(
        implementation["schema"] == "v35_committed_task_implementation.v1"
        and implementation["committed_files"] == list(FILES)
        and implementation["inherited_V34_files"] == list(original["sha256"])
        and implementation["inherited_V34_implementation"]
        == entry(V34_ROOT / "implementation/record.json")
        and list(implementation["sha256"]) == [*FILES, *original["sha256"]]
        and len(implementation["source_commit"]) == 40,
        "V35 implementation binding or freeze order changed",
    )
    for name, expected in implementation["sha256"].items():
        require(
            sha(Path(root) / "implementation" / name) == expected,
            "frozen implementation bytes changed",
        )
        if name in original["sha256"]:
            require(expected == original["sha256"][name], "inherited V34 source differs")
    return implementation


def frozen_tail_worker(root=ROOT):
    """Verified old numerical loader; importing it constructs no CUDA context."""
    root = Path(root)
    checked_implementation(root)
    directory = root / "implementation"
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    for name in ("finqa_v34_tail_controller", "finqa_v34_tail_worker"):
        path = directory / (name + ".py")
        old = sys.modules.get(name)
        if old is not None:
            require(sha(old.__file__) == sha(path), "different helper module already imported")
        else:
            _module(path, name)
    return sys.modules["finqa_v34_tail_worker"]


def frozen_cache_module(root=ROOT):
    path = Path(root) / "implementation" / FILES[2]
    implementation = checked_implementation(root)
    require(sha(path) == implementation["sha256"][path.name], "cache bytes changed")
    return _module(path, __name__ + "_cache")


def authorization_body(root):
    audit = entry(Path(root) / "audit/record.json")
    return dict(
        schema="v35_explicit_whole_task_supplement_authorization.v1",
        user_date="2026-10-10",
        user_request="参照审计修订并开展后续实验",
        previous_resource_permission="本轮实验可以占用额外的空闲显卡",
        audit=audit,
        audited_repository_commit=AUDITED_COMMIT,
        scope="one complete-task class pass across four static shards, durable task caches, "
        "then one global recomputation from saved V33 gJ",
        original_B_resume_authorized=False,
        no_automatic_retry=True,
        previous_trial_closeout=entry(V34_ROOT / "closeout_01/record.json"),
    )


def check_task_scope(task_plan):
    """Require the full production input scope, not merely plausible counts."""
    tasks = task_plan["tasks"]
    identifiers = task_plan["task_ids"]
    assignments = task_plan["assignments"]
    specs = task_plan["parameter_spec"]
    require(
        len(identifiers) == len(set(identifiers)) == len(tasks) == 744
        and [task["task_id"] for task in tasks] == identifiers
        and [task["index"] for task in tasks] == list(range(744))
        and task_plan["state_count"] == sum(len(task["state_ids"]) for task in tasks) == 1360
        and task_plan["package_count"] == sum(len(task["packages"]) for task in tasks) == 2468
        and task_plan["row_count"] == sum(task["row_count"] for task in tasks) == 4974
        and task_plan["row_count"]
        == sum(package["row_count"] for task in tasks for package in task["packages"]),
        "actual scientific task/state/package/row scope changed",
    )
    require(
        task_plan["shards"] == 4
        and len(assignments) == 4
        and [assignment["shard"] for assignment in assignments] == list(range(4))
        and all(type(task["shard"]) is int and 0 <= task["shard"] < 4 for task in tasks),
        "exactly four canonical complete-task shard assignments required",
    )
    for shard, assignment in enumerate(assignments):
        selected = [task for task in tasks if task["shard"] == shard]
        require(
            bool(selected)
            and assignment["task_ids"] == [task["task_id"] for task in selected]
            and assignment["task_indices"] == [task["index"] for task in selected]
            and assignment["row_count"] == sum(task["row_count"] for task in selected),
            "shard assignment must cover its exact original-order whole tasks",
        )
    require(
        len(specs) == len({item["name"] for item in specs}) == 112
        and all(item["dtype"] == "torch.float32" for item in specs),
        "production requires exactly 112 ordered FP32 trainable parameter coordinates",
    )
    return task_plan


def make_plan_and_binding(root, common, implementation):
    tail = frozen_tail_worker(root)
    training, rt, _inherited, _guard, _pause, _memory, mechanism, _immutable = tail.dependencies()
    require(not rt.torch.cuda.is_initialized(), "registration cannot initialize CUDA")
    _record, _inputs, actual = mechanism.checked_outer(common["source_outer"]["path"])
    _, pool, _, _ = training.checked_launch(training.DEFAULT_ROOT)
    parameter_spec = [
        dict(name=name, shape=list(value.shape), dtype=str(value.dtype))
        for name, value in actual["pre_state"]["parameters"].items()
    ]
    cache = frozen_cache_module(root)
    task_plan = cache.make_task_plan(pool, parameter_spec, shards=4)
    check_task_scope(task_plan)
    task_plan = publish(
        Path(root) / "task_plan/record.json",
        {key: value for key, value in task_plan.items() if key != "id"},
    )
    binding = dict(
        schema="v35_exact_task_gradient_math_binding.v1",
        task_plan_id=task_plan["id"],
        implementation_id=implementation["id"],
        source_outer=common["source_outer"],
        benchmark_manifest=common["benchmark_manifest"],
        pre_state_digest=rt.v8._tree_digest(actual["pre_state"]),
        point_id=actual["point_id"],
        saved_gJ_digest=common["saved_gJ_digest"],
        source_final_checkpoint=common["source_final_checkpoint"],
        source_final_checkpoint_state=common["source_final_checkpoint_state"],
        storage_source=file_ref(Path(root) / "implementation/finqa_v34_tail_memory.py"),
        original_class_source=file_ref(rt.v8.__file__),
        original_B_resume_authorized=False,
    )
    require(not rt.torch.cuda.is_initialized(), "CPU task planning created a CUDA context")
    return task_plan, binding


def protocol_body(common, implementation, root, *, at, observed, task_binding):
    root = Path(root)
    body = copy.deepcopy({key: value for key, value in common.items() if key != "id"})
    for key in (
        "fixed_gpu_index",
        "fixed_gpu_uuid",
        "stage_timeout_seconds",
        "tail_supplement_validation_count",
        "fresh_tail_process",
    ):
        body.pop(key, None)
    body.update(
        schema="v35_bounded_whole_task_protocol.v1",
        at=at,
        source_commit=implementation["source_commit"],
        output_root=str(root),
        implementation_id=implementation["id"],
        inherited_V34_protocol=entry(V34_ROOT / "protocol/record.json"),
        authorization=entry(root / "authorization/record.json"),
        previous_trial_closeout=entry(V34_ROOT / "closeout_01/record.json"),
        audit=entry(root / "audit/record.json"),
        audited_repository_commit=AUDITED_COMMIT,
        task_plan=entry(root / "task_plan/record.json"),
        task_binding=task_binding,
        task_cache_root=str(root / "task_cache"),
        stages=list(STAGES),
        stage_gpu_index=STAGE_GPU,
        allowed_gpu_indices=list(ALLOWED_GPUS),
        maximum_workers=4,
        max_gpu_workers=4,
        maximum_gpu_workers_including_CPU_initialization=4,
        paired_stages_same_physical_gpu=False,
        paired_response_replay_stages_present=False,
        CPU_initialization_counts_as_worker=True,
        maximum_workers_per_gpu=1,
        coordinator_gpu_index=7,
        coordinator_requires_all_shard_processes_exited=True,
        coordinator_requires_all_task_caches_validated=True,
        coordinator_runs=1,
        task_count=744,
        state_count=1360,
        package_count=2468,
        row_count=4974,
        parameter_count=112,
        parameter_dtype="torch.float32",
        class_gradient_passes=1,
        shard_passes_are_disjoint_whole_tasks=True,
        package_state_and_parameter_reduction_order_unchanged=True,
        global_mu_and_original_package_denominators_unchanged=True,
        no_local_optimizer_or_shard_C_pi=True,
        no_DDP_or_gradient_averaging=True,
        completed_V34_rows_reused=0,
        candidate_variant="whole_task_sharded_tail",
        candidate_change="whole-task scheduling and immutable task caches only; same V34 storage",
        tail_storage_source=file_ref(root / "implementation/finqa_v34_tail_memory.py"),
        task_storage_source=file_ref(root / "implementation" / FILES[2]),
        gpu_observation_at_registration=observed,
        global_deadline_seconds=GLOBAL_DEADLINE_SECONDS,
        global_clock_starts="immediately before first successful GPU-worker Popen",
        all_shards_and_coordinator_share_one_deadline=True,
        termination_grace_seconds=TERM_GRACE_SECONDS,
        scheduled_worker_hours_upper_bound=4 * GLOBAL_DEADLINE_SECONDS / 3600,
        shutdown_grace_seconds=TERM_GRACE_SECONDS,
        shutdown_grace_worker_hours_upper_bound=4 * TERM_GRACE_SECONDS / 3600,
        grace_does_not_authorize_new_tasks=True,
        scheduled_worker_hours_excludes_shutdown_grace=True,
        grace_is_one_shared_window_not_per_worker=True,
        resource_wait_budget_seconds=WAIT_BUDGET_SECONDS,
        resource_wait_after_first_launch_counts_toward_global_deadline=True,
        host_ram=copy.deepcopy(HOST_RAM),
        disk_admission="twice raw complete-class tensor bytes plus 32GiB free reserve",
        maximum_allocated_bytes=MAXIMUM_ALLOCATED_BYTES,
        minimum_device_free_bytes=MINIMUM_DEVICE_FREE_BYTES,
        API_calls=0,
        API_model_if_ever_authorized="deepseek-flash",
        new_sampling_calls=0,
        scoring_calls=0,
        optimizer_steps=0,
        replayed_responses=0,
        automatic_retry=False,
        automatic_resource_fallback=False,
        further_class_passes_authorized=False,
        original_B_resume_authorized=False,
        original_V34_protocol_or_results_may_be_modified=False,
        original_V34_failure_reclassified=False,
    )
    return body


def initialize(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "one new V35 destination; never overwrite/restart")
    common = inherited_protocol()
    observed = inventory()
    require(
        {str(row["index"]): row["uuid"] for row in observed if row["index"] in ALLOWED_GPUS}
        == common["gpu_uuids"],
        "registered physical GPU identities changed",
    )
    implementation = _freeze(root, source_commit)
    raw = AUDIT_ATTACHMENT.read_bytes()
    audit_path = root / "audit/source.txt"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    publish(
        root / "audit/record.json",
        dict(
            schema="v35_supplied_audit_text.v1",
            at=now(),
            source=file_ref(audit_path),
            original_attachment=file_ref(AUDIT_ATTACHMENT),
            audited_repository_commit=AUDITED_COMMIT,
            linked_zip_or_standalone_report_supplied=False,
            remote_CPU_claims_are_not_local_test_results=True,
            remote_offline_statement_is_not_a_server_admission_result=True,
        ),
    )
    publish(root / "authorization/record.json", authorization_body(root))
    _task_plan, binding = make_plan_and_binding(root, common, implementation)
    protocol = publish(
        root / "protocol/record.json",
        protocol_body(
            common,
            implementation,
            root,
            at=now(),
            observed=observed,
            task_binding=binding,
        ),
    )
    status(
        root,
        dict(
            phase="REGISTERED_NOT_STARTED",
            protocol_id=protocol["id"],
            active_children=[],
            original_B_resume_authorized=False,
        ),
    )
    return protocol


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "fixed V35 destination required")
    common = inherited_protocol()
    implementation = checked_implementation(root)
    protocol = checked(root / "protocol/record.json")
    authorization = checked(root / "authorization/record.json")
    require(
        {k: v for k, v in authorization.items() if k != "id"} == authorization_body(root),
        "V35 authorized scope changed",
    )
    audit = read_ref(protocol["audit"])
    require(
        sha(audit["source"]["path"])
        == audit["source"]["sha256"]
        == audit["original_attachment"]["sha256"],
        "audit source bytes changed",
    )
    task_plan = read_ref(protocol["task_plan"])
    binding = protocol["task_binding"]
    require(
        binding["task_plan_id"] == task_plan["id"]
        and binding["implementation_id"] == implementation["id"]
        and binding["source_outer"] == common["source_outer"]
        and binding["benchmark_manifest"] == common["benchmark_manifest"]
        and binding["source_final_checkpoint"] == common["source_final_checkpoint"]
        and binding["source_final_checkpoint_state"] == common["source_final_checkpoint_state"]
        and binding["saved_gJ_digest"] == common["saved_gJ_digest"]
        and binding["storage_source"] == file_ref(root / "implementation/finqa_v34_tail_memory.py")
        and sha(binding["original_class_source"]["path"])
        == binding["original_class_source"]["sha256"]
        and binding["original_B_resume_authorized"] is False,
        "mathematical task cache binding changed",
    )
    expected = protocol_body(
        common,
        implementation,
        root,
        at=protocol["at"],
        observed=protocol["gpu_observation_at_registration"],
        task_binding=binding,
    )
    require(
        {key: value for key, value in protocol.items() if key != "id"} == expected,
        "fixed V35 contract changed",
    )
    check_task_scope(task_plan)
    verify_original_B_paused(protocol)
    return protocol


def eligible(row, protocol):
    return (
        row["index"] in ALLOWED_GPUS
        and row["uuid"] == protocol["gpu_uuids"].get(str(row["index"]))
        and not row["processes"]
        and row["free_mib"] >= MINIMUM_FREE_MIB
    )


def host_memory():
    fields = {
        line.split(":", 1)[0]: int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
    }
    available = fields["MemAvailable"]
    ancestors = []
    cgroup = next(
        (
            line.split(":", 2)[2]
            for line in Path("/proc/self/cgroup").read_text().splitlines()
            if line.startswith("0::")
        ),
        None,
    )
    if cgroup is not None:
        base = Path("/sys/fs/cgroup")
        path = base / cgroup.lstrip("/")
        while path == base or base in path.parents:
            limit_path, current_path = path / "memory.max", path / "memory.current"
            if limit_path.exists() and current_path.exists():
                limit = limit_path.read_text().strip()
                current = int(current_path.read_text().strip())
                ancestors.append(dict(path=str(path), memory_max=limit, memory_current=current))
                if limit != "max":
                    available = min(available, max(0, int(limit) - current))
            if path == base:
                break
            path = path.parent
    return dict(
        total_bytes=fields["MemTotal"],
        available_bytes=available,
        physical_mem_available_bytes=fields["MemAvailable"],
        cgroup_ancestors=ancestors,
    )


def disk_memory(root, task_plan):
    parameter_bytes = sum(
        math.prod(item["shape"]) * {"torch.float32": 4, "torch.float64": 8}[item["dtype"]]
        for item in task_plan["parameter_spec"]
    )
    states = sum(len(task["state_ids"]) for task in task_plan["tasks"])
    expected = parameter_bytes * states
    return dict(
        free_bytes=shutil.disk_usage(root).free,
        estimated_class_tensor_bytes=expected,
        admission_bytes=2 * expected + 32 * GIB,
    )


def process_memory(pid):
    try:
        rows = Path(f"/proc/{pid}/status").read_text().splitlines()
    except (FileNotFoundError, ProcessLookupError):
        return None
    fields = {
        line.split(":", 1)[0]: int(line.split()[1]) * 1024
        for line in rows
        if line.startswith(("VmRSS:", "VmHWM:"))
    }
    if "VmRSS" not in fields:
        return None
    return dict(rss_bytes=fields["VmRSS"], peak_rss_bytes=fields["VmHWM"])


def check_resources(resources, *, coordinator):
    # Reuse the sealed V34 exact gate validator, only adapt phase labels.
    expected_labels = {"after_model_load.after_cleanup", "after_distribution.after_cleanup"}
    if not coordinator:
        expected_labels = {"after_model_load.after_cleanup", "shard_complete.after_cleanup"}
    observations = resources.get("observations", [])
    require(
        expected_labels <= {row["label"] for row in observations if row["boundary"]},
        "missing complete stage resource boundaries",
    )
    adapted = copy.deepcopy(resources)
    # V34's validator also requires a class-completion boundary. No numerical
    # class pass is claimed here: duplicate a validated real final boundary only
    # inside this private adapter, never in persisted telemetry.
    final = next(
        row
        for row in observations
        if row["label"] in expected_labels - {"after_model_load.after_cleanup"}
    )
    for label in ("class_gradients_complete.after_cleanup", "after_distribution.after_cleanup"):
        if not any(row["label"] == label for row in adapted["observations"]):
            adapted["observations"].append(dict(final, label=label))
    fixture = dict(
        stage=_common.STAGE,
        protocol_id="resource-only",
        status="COMPLETE",
        numeric_pass=True,
        backend_version=BACKEND_VERSION,
        API_calls=0,
        new_sampling_calls=0,
        scoring_calls=0,
        optimizer_steps=0,
        replayed_responses=0,
        class_gradient_passes=1,
        reused_completed_responses=573,
        original_B_resume_authorized=False,
        comparison=dict.fromkeys(COHORT_COMPARISON_KEYS, True),
        resources=adapted,
    )
    _common.check_result(dict(id="resource-only"), _common.STAGE, fixture)
    host = resources["host"]
    limit = HOST_RAM["coordinator_rss_limit_bytes" if coordinator else "shard_rss_limit_bytes"]
    require(
        host["rss_limit_bytes"] == limit
        and host["available_reserve_bytes"] == HOST_RAM["reserve_bytes"]
        and host["all_passed"] is True,
        "host RAM limit or combined host gate changed",
    )
    for row in observations:
        value = row["host"]
        require(
            row["deadline_pass"] is True
            and value["rss_limit_bytes"] == limit
            and value["available_reserve_bytes"] == HOST_RAM["reserve_bytes"]
            and value["rss_pass"] is True
            and value["available_pass"] is True
            and value["passed"] is True
            and all(
                type(value[key]) is int and value[key] >= 0
                for key in ("rss_bytes", "peak_rss_bytes", "available_bytes")
            )
            and value["rss_bytes"] <= value["peak_rss_bytes"] <= limit
            and value["available_bytes"] >= HOST_RAM["reserve_bytes"],
            "observed host RAM or global deadline gate failed",
        )
    require(
        host["max_observed_peak_rss_bytes"]
        == max(row["host"]["peak_rss_bytes"] for row in observations)
        and host["min_observed_available_bytes"]
        == min(row["host"]["available_bytes"] for row in observations),
        "host resource summary contradicts exact observations",
    )


def check_result(protocol, stage, result, task_plan):
    require(
        stage in STAGES
        and result["stage"] == stage
        and result["protocol_id"] == protocol["id"]
        and result["status"] == "COMPLETE",
        "foreign, failed or incomplete stage; no retry",
    )
    require(
        result["backend_version"] == BACKEND_VERSION
        and result["original_B_resume_authorized"] is False,
        "changed backend or original B authorization",
    )
    require(
        all(
            type(result[key]) is int and result[key] == 0
            for key in (
                "API_calls",
                "new_sampling_calls",
                "scoring_calls",
                "optimizer_steps",
                "replayed_responses",
            )
        ),
        "unauthorized scientific work",
    )
    require(
        result["gpu_index"] == STAGE_GPU[stage]
        and result["gpu_uuid"] == protocol["gpu_uuids"][str(STAGE_GPU[stage])],
        "stage ran on wrong physical GPU",
    )
    if stage in SHARD_STAGES:
        assignment = task_plan["assignments"][SHARD_STAGES.index(stage)]
        require(
            result["task_ids"] == assignment["task_ids"]
            and type(result["task_count"]) is int
            and result["task_count"] == len(assignment["task_ids"]),
            "shard task ownership or completion mismatch",
        )
        require(
            type(result["class_gradient_passes"]) is int
            and result["class_gradient_passes"] == 0
            and result["global_class_gradient_pass_contribution"] is True
            and result["model_optimizer_rng_buffers_existing_grad_unchanged"] is True
            and type(result["class_task_calls"]) is int
            and result["class_task_calls"] >= 0
            and len(set(result["reused_task_ids"])) == len(result["reused_task_ids"])
            and set(result["reused_task_ids"]) <= set(assignment["task_ids"])
            and result["class_task_calls"] + len(result["reused_task_ids"]) == result["task_count"],
            "shard mutated state or performed extra full class pass",
        )
    else:
        require(
            result["numeric_pass"] is True
            and all(result["comparison"].get(key) is True for key in COHORT_COMPARISON_KEYS)
            and all(value is True for value in result["comparison"].values()),
            "all eight independent numerical comparisons must pass",
        )
        require(
            type(result["class_gradient_passes"]) is int
            and result["class_gradient_passes"] == 0
            and type(result["global_class_gradient_passes"]) is int
            and result["global_class_gradient_passes"] == 1
            and result["reused_completed_responses"] == 573
            and result["task_count"] == 744
            and result["state_count"] == 1360,
            "coordinator must reuse all task caches and saved responses without new class pass",
        )
    check_resources(result["resources"], coordinator=stage == "coordinator")
    return result


def worker_command(root, stage, row, protocol, deadline_epoch):
    require(stage in STAGES and row["index"] == STAGE_GPU[stage], "unregistered GPU/stage")
    command = _common._common.worker_command(root, stage, row, protocol)
    command[5] = str(Path(root) / "implementation" / FILES[1])
    return [*command, "--deadline-epoch", str(deadline_epoch)]


class Controller:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.protocol = checked_protocol(self.root)
        self.task_plan = read_ref(self.protocol["task_plan"])
        self.active = {}
        self.results = {}
        self.wait_used = 0.0
        self.stop = False
        self.deadline = None
        self.deadline_epoch = None
        self.first_launch_epoch = None
        self.host_event_count = 0

    def update(self, phase, **extra):
        status(
            self.root,
            dict(
                phase=phase,
                protocol_id=self.protocol["id"],
                resource_wait_seconds=self.wait_used,
                active_children=[
                    {
                        key: item["launch"][key]
                        for key in ("stage", "pid", "birth", "gpu_index", "gpu_uuid")
                    }
                    for item in self.active.values()
                ],
                first_launch_epoch=self.first_launch_epoch,
                global_deadline_epoch=self.deadline_epoch,
                worker_accounting=self.worker_accounting(),
                completed_stages=list(self.results),
                original_B_resume_authorized=False,
                **extra,
            ),
        )

    def worker_accounting(self):
        """Observed worker lifetimes include CPU initialization and exit grace."""
        exits = [
            checked(self.root / stage / "exit/record.json")
            for stage in STAGES
            if (self.root / stage / "exit/record.json").is_file()
        ]
        seconds = sum(row["elapsed_worker_wall_seconds"] for row in exits)
        return dict(
            total_elapsed_worker_wall_seconds=seconds,
            total_elapsed_worker_hours=seconds / 3600,
            exited_worker_count=len(exits),
            active_worker_count=len(self.active),
            active_worker_lifetimes_not_yet_in_sum=bool(self.active),
            includes_CPU_initialization_and_shutdown_grace=True,
            basis=(
                "Popen submission to observed process exit; "
                "includes polling latency, not GPU compute time"
            ),
        )

    def time_gate(self):
        require(not self.stop, "controller stop requested")
        require(self.wait_used < WAIT_BUDGET_SECONDS, "24-hour cumulative resource wait exhausted")
        require(
            self.deadline is None or time.monotonic() < self.deadline,
            "four-hour shared global deadline exhausted",
        )

    def observe_host(self):
        memory = host_memory()
        processes = []
        for stage, item in self.active.items():
            launch = item["launch"]
            if item["process"].poll() is not None:
                continue
            require(birth(launch["pid"]) == launch["birth"], "live worker ownership changed")
            observed = process_memory(launch["pid"])
            if observed is None:  # Reaped at this observation boundary; checked by poll next.
                require(item["process"].poll() is not None, "live worker RSS unavailable")
                continue
            limit = HOST_RAM[
                "coordinator_rss_limit_bytes" if stage == "coordinator" else "shard_rss_limit_bytes"
            ]
            processes.append(
                dict(
                    stage=stage,
                    pid=launch["pid"],
                    birth=launch["birth"],
                    **observed,
                    rss_limit_bytes=limit,
                    passed=max(observed.values()) <= limit,
                )
            )
        passed = memory["available_bytes"] >= HOST_RAM["reserve_bytes"] and all(
            row["passed"] for row in processes
        )
        publish(
            self.root / "host_resources" / f"event{self.host_event_count:06d}/record.json",
            dict(
                schema="v35_observed_host_resource_gate.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                **memory,
                reserve_bytes=HOST_RAM["reserve_bytes"],
                processes=processes,
                passed=passed,
                observation_not_allocation_guarantee=True,
                independent_pinned_cap=False,
            ),
        )
        self.host_event_count += 1
        require(passed, "observed host RSS or MemAvailable hard gate failed")

    def acquire(self, stages):
        indices = [STAGE_GPU[stage] for stage in stages]
        admission = HOST_RAM[
            "coordinator_admission_bytes" if stages == ("coordinator",) else "shard_admission_bytes"
        ]
        while True:
            self.time_gate()
            started = time.monotonic()
            rows = {row["index"]: row for row in inventory()}
            memory = host_memory()
            disk = disk_memory(self.root, self.task_plan)
            require(
                disk["free_bytes"] >= disk["admission_bytes"],
                "insufficient disk for durable complete-task caches and reserve",
            )
            locks = {}
            if memory["available_bytes"] >= admission and all(
                index in rows and eligible(rows[index], self.protocol) for index in indices
            ):
                try:
                    for index in indices:
                        path = self.root / "locks" / ("gpu-" + rows[index]["uuid"] + ".lock")
                        path.parent.mkdir(parents=True, exist_ok=True)
                        lock = path.open("a")
                        locks[index] = lock
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fresh = {row["index"]: row for row in inventory()}
                    if host_memory()["available_bytes"] >= admission and all(
                        index in fresh and eligible(fresh[index], self.protocol)
                        for index in indices
                    ):
                        self.wait_used += time.monotonic() - started
                        self.time_gate()
                        return fresh, locks
                except BlockingIOError:
                    pass
                except BaseException:
                    for lock in locks.values():
                        lock.close()
                    raise
            for lock in locks.values():
                lock.close()
            self.update(
                "WAITING_FOR_IDLE_GPUS_AND_HOST_RAM",
                waiting_stages=list(stages),
                gpu_observation=list(rows.values()),
                host_observation=memory,
                host_admission_bytes=admission,
                disk_observation=disk,
            )
            delay = min(POLL_SECONDS, max(0, WAIT_BUDGET_SECONDS - self.wait_used))
            if self.deadline is not None:
                delay = min(delay, max(0, self.deadline - time.monotonic()))
            time.sleep(delay)
            self.wait_used += time.monotonic() - started

    def launch(self, stage, row, lock):
        self.time_gate()
        require(
            stage not in self.active
            and stage not in self.results
            and not (self.root / stage / "launch/record.json").exists(),
            "stage previously dispatched; no automatic retry",
        )
        require(
            len(self.active) < 4
            and row["index"] == STAGE_GPU[stage]
            and all(item["launch"]["gpu_index"] != row["index"] for item in self.active.values()),
            "worker cap or one-worker-per-GPU gate failed",
        )
        require(
            stage != "coordinator" or not self.active, "coordinator cannot overlap shard workers"
        )
        if stage == "coordinator":
            require(
                set(self.results) == set(SHARD_STAGES)
                and (self.root / "complete_task_cache/record.json").is_file(),
                "coordinator requires every shard exit and sealed complete-task coverage",
            )
        verify_original_B_paused(self.protocol)
        fresh = next((value for value in inventory() if value["index"] == row["index"]), None)
        require(fresh is not None and eligible(fresh, self.protocol), "GPU no longer idle at Popen")
        directory = self.root / stage
        directory.mkdir(parents=True, exist_ok=True)
        if self.deadline is None:
            self.first_launch_epoch = time.time()
            self.deadline_epoch = self.first_launch_epoch + GLOBAL_DEADLINE_SECONDS
            self.deadline = time.monotonic() + GLOBAL_DEADLINE_SECONDS
            publish(
                self.root / "execution_window/record.json",
                dict(
                    schema="v35_one_global_execution_window.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    first_launch_epoch=self.first_launch_epoch,
                    deadline_epoch=self.deadline_epoch,
                    duration_seconds=GLOBAL_DEADLINE_SECONDS,
                    no_stage_deadline_reset=True,
                    no_automatic_restart=True,
                ),
            )
        command = worker_command(self.root, stage, row, self.protocol, self.deadline_epoch)
        started_monotonic, started_epoch = time.monotonic(), time.time()
        with (directory / "worker.log").open("xb") as stream:
            process = subprocess.Popen(
                command,
                cwd=REPO,
                env=worker_environment(row),
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        born = birth(process.pid)
        launch = dict(
            schema="v35_bounded_task_stage_launch.v1",
            at=now(),
            protocol_id=self.protocol["id"],
            stage=stage,
            pid=process.pid,
            birth=born,
            worker=str(self.root / "implementation" / FILES[1]),
            command=command,
            gpu_index=row["index"],
            gpu_uuid=row["uuid"],
            gpu_observed=fresh,
            global_deadline_epoch=self.deadline_epoch,
            global_first_launch_epoch=self.first_launch_epoch,
            popen_started_epoch=started_epoch,
            term_grace_seconds=TERM_GRACE_SECONDS,
        )
        self.active[stage] = dict(
            process=process, launch=launch, lock=lock, started_monotonic=started_monotonic
        )
        require(born is not None, "worker exited before process ownership was established")
        self.active[stage]["launch"] = publish(directory / "launch/record.json", launch)
        self.update("RUNNING", stage=stage)

    def record_exit(self, stage, *, stopped=False):
        item = self.active[stage]
        process = item["process"]
        require(process.poll() is not None, "cannot release a live worker/model")
        code = process.wait()
        elapsed = max(0.0, time.monotonic() - item["started_monotonic"])
        publish(
            self.root / stage / "exit/record.json",
            dict(
                schema="v35_bounded_task_stage_exit.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                stage=stage,
                returncode=code,
                stop_requested=stopped,
                global_deadline_epoch=self.deadline_epoch,
                no_retry=True,
                observed_exit_epoch=time.time(),
                elapsed_worker_wall_seconds=elapsed,
                elapsed_worker_wall_seconds_basis=(
                    "Popen submission to observed exit; includes polling latency"
                ),
                includes_CPU_initialization_and_shutdown_grace=True,
            ),
        )
        item["lock"].close()
        del self.active[stage]
        return code

    def drain_stopped(self):
        """Signal every owned process immediately; use ONE grace for the group."""
        stop_at = time.monotonic()
        signal_errors = []

        def signal_group(sig):
            for item in self.active.values():
                if item["process"].poll() is None:
                    try:
                        signal_owned(item["launch"], sig)
                    except BaseException as error:
                        # One failed identity guard must never prevent the
                        # other verified workers receiving their stop request.
                        signal_errors.append(
                            dict(stage=item["launch"]["stage"], signal=int(sig), error=str(error))
                        )

        signal_group(signal.SIGTERM)
        self.update("SAFE_BOUNDARY_STOP_REQUESTED", shared_stop_started_monotonic=stop_at)
        killed = False
        while self.active:
            for stage in tuple(self.active):
                if self.active[stage]["process"].poll() is not None:
                    self.record_exit(stage, stopped=True)
            if not self.active:
                break
            if time.monotonic() - stop_at >= TERM_GRACE_SECONDS and not killed:
                signal_group(signal.SIGKILL)
                killed = True
            # Never reap sequentially with separate ten-minute grace periods.
            require(
                not killed or time.monotonic() - stop_at < TERM_GRACE_SECONDS + 60,
                "owned process still alive after shared kill window; manual inspection required",
            )
            time.sleep(min(POLL_SECONDS, 1 if killed else POLL_SECONDS))
        require(
            not signal_errors, "one or more verified signal guards failed: " + str(signal_errors)
        )

    def run_group(self, stages):
        rows, locks = self.acquire(stages)
        try:
            for stage in stages:
                index = STAGE_GPU[stage]
                try:
                    self.launch(stage, rows[index], locks[index])
                finally:
                    if stage in self.active:
                        # A post-Popen publication failure still owns a live
                        # process; its GPU lock stays held until global drain.
                        del locks[index]
            while self.active:
                self.time_gate()
                self.observe_host()
                for stage in tuple(self.active):
                    item = self.active[stage]
                    failure = self.root / stage / "failure/record.json"
                    require(not failure.exists(), "worker reported failure: " + stage)
                    if item["process"].poll() is not None:
                        code = self.record_exit(stage)
                        require(code == 0, "worker exited unsuccessfully: " + stage)
                        result = checked(self.root / stage / "result/record.json")
                        self.results[stage] = check_result(
                            self.protocol, stage, result, self.task_plan
                        )
                        self.update("RUNNING")
                if self.active:
                    time.sleep(min(POLL_SECONDS, max(0, self.deadline - time.monotonic())))
            self.time_gate()
        finally:
            for lock in locks.values():
                lock.close()

    def validate_task_coverage(self, *, complete):
        cache_module = frozen_cache_module(self.root)
        records = cache_module.inspect_completed(
            self.root / "task_cache",
            self.protocol["task_binding"],
            self.task_plan,
        )
        completed = [row["task_id"] for row in records]
        missing = [task for task in self.task_plan["task_ids"] if task not in set(completed)]
        if complete:
            require(not missing, "every task cache must be complete before coordinator admission")
        return dict(
            task_plan_id=self.task_plan["id"],
            binding_sha256=digest(self.protocol["task_binding"]),
            task_records=[{k: v for k, v in row.items() if k != "record"} for row in records],
            complete_task_ids=completed,
            missing_task_ids=missing,
            complete_task_count=len(completed),
            total_task_count=len(self.task_plan["task_ids"]),
            tensor_deserialization_and_finite_checks_required_in_coordinator_before_CUDA=True,
        )

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run only the frozen committed V35 controller",
        )
        path = self.root / "queue/controller.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            publish(
                self.root / "queue/run_intent/record.json",
                dict(
                    schema="v35_bounded_task_controller_intent.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    pid=os.getpid(),
                    birth=birth(os.getpid()),
                    no_automatic_controller_restart=True,
                ),
            )
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
            for sig in handlers:
                signal.signal(sig, lambda *_: setattr(self, "stop", True))
            try:
                self.run_group(SHARD_STAGES)
                require(
                    not self.active and set(self.results) == set(SHARD_STAGES),
                    "all four shard processes must exit before coordinator",
                )
                self.time_gate()
                coverage = self.validate_task_coverage(complete=True)
                self.time_gate()
                publish(
                    self.root / "complete_task_cache/record.json",
                    dict(
                        schema="v35_all_tasks_complete_before_coordinator.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        all_shard_processes_exited=True,
                        **coverage,
                    ),
                )
                self.run_group(("coordinator",))
                publish(
                    self.root / "result/record.json",
                    dict(
                        schema="v35_completed_task_sharded_supplement.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        status="COMPLETE",
                        numeric_pass=True,
                        coordinator_result=entry(self.root / "coordinator/result/record.json"),
                        task_cache_complete=entry(self.root / "complete_task_cache/record.json"),
                        task_count=744,
                        state_count=1360,
                        class_gradient_passes=1,
                        global_recomputations=1,
                        API_calls=0,
                        new_sampling_calls=0,
                        scoring_calls=0,
                        optimizer_steps=0,
                        replayed_responses=0,
                        reused_completed_responses=573,
                        original_B_resume_authorized=False,
                        original_V34_failure_reclassified=False,
                        worker_accounting=self.worker_accounting(),
                    ),
                )
                self.update("COMPLETE", supplement_validation_complete=True)
                return True
            except BaseException as error:
                stop_error = None
                try:
                    self.drain_stopped()
                except BaseException as drain_error:
                    stop_error = dict(error_type=type(drain_error).__name__, error=str(drain_error))
                try:
                    coverage = self.validate_task_coverage(complete=False)
                except BaseException as cache_error:
                    coverage = dict(
                        cache_validation_failed=True,
                        error_type=type(cache_error).__name__,
                        error=str(cache_error),
                        remaining_tasks_not_claimed_complete=True,
                    )
                body = dict(
                    error_type=type(error).__name__,
                    error=str(error),
                    stop_error=stop_error,
                    task_cache_coverage=coverage,
                    worker_lifetime_accounting=self.worker_accounting(),
                    no_automatic_retry=True,
                    no_implicit_fallback=True,
                    original_B_resume_authorized=False,
                )
                self.update(
                    "STOPPED_FAILURE_NO_RETRY",
                    **{k: v for k, v in body.items() if k != "original_B_resume_authorized"},
                )
                publish(
                    self.root / "failure/record.json",
                    dict(
                        schema="v35_bounded_task_failure.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        **body,
                    ),
                )
                raise
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "run", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.action == "initialize":
        require(args.source_commit is not None, "committed source required")
        result = initialize(args.root, source_commit=args.source_commit)
        print(json.dumps(dict(id=result["id"], status="REGISTERED_NOT_STARTED")))
    elif args.action == "run":
        Controller(args.root).run()
    else:
        result = checked_protocol(args.root)
        print(
            json.dumps(
                dict(
                    id=result["id"],
                    gpu_observation=inventory(),
                    host_observation=host_memory(),
                    original_B_resume_authorized=False,
                )
            )
        )


if __name__ == "__main__":
    main()
