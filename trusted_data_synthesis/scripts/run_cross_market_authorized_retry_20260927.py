"""User-authorized attempts 5 and 6 for exactly one exhausted generation shard.

The original scientific and performance protocols stay immutable. A private
coordinator copy changes only the cap lookup for the registered job identity.
"""

import argparse
import ast
import copy
import inspect
import json
import os
import subprocess
import textwrap
from pathlib import Path

import run_cross_market_performance_20260927 as performance

previous, recovery, p = performance.previous, performance.recovery, performance.p
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_authorized_retry_20260927.py"
DIRECTORY = "authorized_retry_01"
PROTOCOL = "cross_market_authorized_shard_retry_protocol"
TARGET = "generate_negative_11_stochastic_0"
ORIGINAL_ATTEMPTS = 4
ADDITIONAL_ATTEMPTS = 2
_HELPER = "_authorized_attempt_cap"
_CAP = """
cap = plan["scheduling"][
    "scoring_attempts_per_cohort" if scores_allowed else "generation_attempts_per_shard"
]
"""


def require(condition, reason):
    p.require(condition, "cross_market_authorized_retry." + reason)


def attempt_cap(job, original_cap, target_job_id):
    if job["key"] != TARGET:
        return original_cap
    require(
        job["id"] == target_job_id
        and job["work_kind"] == "generate"
        and original_cap == ORIGINAL_ATTEMPTS,
        "exact_target_identity_and_original_cap",
    )
    return original_cap + ADDITIONAL_ATTEMPTS


def coordinate_with_extra_attempts(namespace, target_job_id):
    original = ast.parse(textwrap.dedent(inspect.getsource(previous.coordinate)))
    expected = ast.parse(textwrap.dedent(_CAP)).body[0]

    def dump(node):
        return ast.dump(node, include_attributes=False)

    matches = [node for node in ast.walk(original) if dump(node) == dump(expected)]
    require(len(matches) == 1 and _HELPER not in namespace, "one_original_cap_assignment")
    changed = copy.deepcopy(original)
    selected = next(node for node in ast.walk(changed) if dump(node) == dump(expected))
    selected.value = ast.Call(
        func=ast.Name(id=_HELPER, ctx=ast.Load()),
        args=[ast.Name(id="job", ctx=ast.Load()), selected.value],
        keywords=[],
    )
    restored = copy.deepcopy(changed)
    calls = [
        node
        for node in ast.walk(restored)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _HELPER
    ]
    require(len(calls) == 1, "one_new_cap_call")
    assignment = next(
        node
        for node in ast.walk(restored)
        if isinstance(node, ast.Assign) and node.value is calls[0]
    )
    assignment.value = calls[0].args[1]
    require(dump(restored) == dump(original), "all_other_coordinator_AST_unchanged")
    namespace[_HELPER] = lambda job, cap: attempt_cap(job, cap, target_job_id)
    code = compile(
        ast.fix_missing_locations(changed), str(Path(previous.__file__)) + "[retry]", "exec"
    )
    exec(code, namespace)
    result = namespace["coordinate"]
    result.authorized_retry_binding = dict(
        source_sha256=p.sha(Path(previous.__file__)),
        original_ast_sha256=p.sha(dump(original).encode()),
        adapted_ast_sha256=p.sha(dump(changed).encode()),
        changed_cap_assignment_count=1,
        all_other_AST_unchanged=True,
    )
    return result


def target_job(c, original):
    job = p.checked(
        p.read_json(c.RAW / "jobspecs" / (TARGET + ".json")),
        "cross_market_evaluation_work_unit",
    )
    require(
        job["key"] == TARGET
        and job["work_kind"] == "generate"
        and job["protocol_id"] == original["id"],
        "fixed_registered_generation_shard",
    )
    return job


def validate_original_failures(c, job, entries):
    require([entry["attempt"] for entry in entries] == [1, 2, 3, 4], "exact_four_failures")
    history = {row["attempt"]: row for row in previous.attempts(c, job)}
    for entry in entries:
        row = history.get(entry["attempt"])
        require(
            row is not None and not row["alive"] and recovery.failure_entry(c, job, row) == entry,
            "unchanged_original_failure_artifacts",
        )
        outcome = row["outcome"]
        require(
            recovery.missing_cublas(job, outcome)
            if entry["attempt"] == 1
            else (
                outcome is not None
                and outcome["status"] == "RESOURCE_RETRY"
                and outcome["exception_type"] == "CapacityWait"
            ),
            "only_original_cublas_and_capacity_failures",
        )


def gpu_allocation(c):
    """Bind the explicit resource release; freed GPUs cannot be reacquired."""
    directory = c.RAW / "gpu_release_01"
    released = p.checked(
        p.read_json(directory / "released.json"), "cross_market_user_GPU_release_completed"
    )
    request = p.checked(
        recovery.checked_reference(released["request"]), "cross_market_user_GPU_release"
    )
    allowed, excluded = request["remaining_allowed_gpu_uuids"], request["released_gpu_uuids"]
    require(
        request["remaining_allowed_gpu_indices"] == [0, 1, 6, 7]
        and request["released_gpu_indices"] == [2, 3, 4, 5]
        and len(allowed) == len(set(allowed)) == len(excluded) == len(set(excluded)) == 4
        and not set(allowed).intersection(excluded)
        and released["process_exits_verified"] is True
        and set(released["stopped_worker_pids"])
        == {item["process"]["pid"] for item in request["target_workers"]}
        and all(
            previous.process_identity(item["process"]["pid"]) != item["process"]["process_identity"]
            for item in request["target_workers"]
        ),
        "four_explicit_released_cards_and_remaining_allowlist",
    )
    return dict(
        allowed_gpu_indices=[0, 1, 6, 7],
        allowed_gpu_uuids=allowed,
        released_gpu_indices=[2, 3, 4, 5],
        released_gpu_uuids=excluded,
        max_GPU_workers=4,
        no_automatic_reacquisition=True,
        release_request=recovery.reference(directory / "request.json"),
        release_completed=recovery.reference(directory / "released.json"),
    )


def register(root, raw=None):
    root, c = Path(root).resolve(), performance.context(raw)
    with c.locked(c.RAW / "control/coordinator.lock", blocking=False):
        if (c.RAW / DIRECTORY / "protocol.json").exists():
            return protocol(root, c.RAW)
        original = c.read_protocol(root)
        parent = performance.protocol(root, c.RAW)
        recovered = recovery.protocol(root, c.RAW)
        allocation = gpu_allocation(c)
        job = target_job(c, original)
        rows = previous.attempts(c, job)
        require(
            original["scheduling"]["generation_attempts_per_shard"] == ORIGINAL_ATTEMPTS
            and [row["attempt"] for row in rows] == [1, 2, 3, 4]
            and not (c.RAW / "generation_seal.json").exists()
            and not previous.complete_job(job),
            "exhausted_unfinished_target_before_private_scoring",
        )
        failures = [recovery.failure_entry(c, job, row) for row in rows]
        validate_original_failures(c, job, failures)
        budget = c._budget_state()
        require(
            budget["counts"]["worker_start"] + ADDITIONAL_ATTEMPTS
            <= original["physical_budget"]["worker_start_cap"],
            "no_global_worker_budget_extension",
        )
        inherited = []
        for path in sorted((c.RAW / "jobspecs").glob("*.json")):
            item = p.read_json(path)
            for row in previous.attempts(c, item):
                if row["alive"]:
                    require(
                        row["reserved"]["gpu"] in allocation["allowed_gpu_uuids"],
                        "only_allowed_cards_have_inherited_workers",
                    )
                    inherited.append(dict(job_key=item["key"], **row))
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        source = (root / SCRIPT).read_bytes()
        require(
            source == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
            "committed_retry_source_before_registration",
        )
        namespace = performance.controller_namespace(parent, recovered)
        binding = coordinate_with_extra_attempts(namespace, job["id"]).authorized_retry_binding
        value = p.record(
            PROTOCOL,
            frozen=True,
            at=p.now(),
            authorization=dict(
                actor="user",
                decision="批准",
                annotation_index=1,
                scope="Only this exhausted shard receives at most two additional attempts",
            ),
            evaluation_protocol=recovery.reference(c.RAW / "protocol.json"),
            evaluation_protocol_id=original["id"],
            performance_protocol=recovery.reference(
                c.RAW / performance.DIRECTORY / "protocol.json"
            ),
            performance_protocol_id=parent["id"],
            target_job=recovery.reference(c.RAW / "jobspecs" / (TARGET + ".json")),
            target_job_id=job["id"],
            target_job_key=TARGET,
            original_attempt_cap=ORIGINAL_ATTEMPTS,
            additional_attempts=ADDITIONAL_ATTEMPTS,
            authorized_attempt_numbers=[5, 6],
            maximum_attempt_number=6,
            original_failures=failures,
            gpu_allocation=allocation,
            original_physical_budget=original["physical_budget"],
            registered_budget_snapshot=copy.deepcopy(budget),
            inherited_active_workers=inherited,
            code_commit=head,
            sources={SCRIPT: p.sha(source)},
            coordinator_binding=binding,
            original_records_and_committed_sessions_preserved=True,
            scientific_protocol_bytes_unchanged=True,
            global_budgets_and_other_shard_attempt_caps_unchanged=True,
            fatal_handling_and_private_scoring_barrier_unchanged=True,
            performance_capacity_and_logprob_policy_inherited=True,
            new_training_updates=0,
            new_API_calls=0,
        )
        return c.write(c.RAW / DIRECTORY / "protocol.json", value)


def protocol(root, raw=None):
    root, c = Path(root).resolve(), performance.context(raw)
    value = p.checked(p.read_json(c.RAW / DIRECTORY / "protocol.json"), PROTOCOL)
    original, parent = c.read_protocol(root), performance.protocol(root, c.RAW)
    job = target_job(c, original)
    require(
        value["frozen"] is True
        and recovery.checked_reference(value["evaluation_protocol"]) == original
        and recovery.checked_reference(value["performance_protocol"]) == parent
        and recovery.checked_reference(value["target_job"]) == job
        and value["target_job_id"] == job["id"]
        and value["target_job_key"] == TARGET
        and value["original_attempt_cap"] == ORIGINAL_ATTEMPTS
        and value["additional_attempts"] == ADDITIONAL_ATTEMPTS
        and value["authorized_attempt_numbers"] == [5, 6]
        and value["maximum_attempt_number"] == 6
        and value["original_physical_budget"] == original["physical_budget"]
        and value["gpu_allocation"] == gpu_allocation(c)
        and value["sources"] == {SCRIPT: p.sha(root / SCRIPT)},
        "same_registered_target_two_attempt_grant_and_parent_protocols",
    )
    validate_original_failures(c, job, value["original_failures"])
    return value


def controller_namespace(plan, performance_plan, recovered):
    namespace = performance.controller_namespace(performance_plan, recovered)
    namespace["SCRIPT"] = SCRIPT
    previous_available = namespace["available_gpus"]
    allowed = frozenset(plan["gpu_allocation"]["allowed_gpu_uuids"])
    require(
        len(allowed) == plan["gpu_allocation"]["max_GPU_workers"] == 4,
        "four_card_coordinator_admission",
    )

    def available_gpus(minimum):
        return [gpu for gpu in previous_available(minimum) if gpu in allowed]

    namespace["available_gpus"] = available_gpus
    function = coordinate_with_extra_attempts(namespace, plan["target_job_id"])
    require(
        function.authorized_retry_binding == plan["coordinator_binding"], "registered_AST_binding"
    )
    namespace["coordinate"] = function
    return namespace


def execute(action, root, raw=None, job=None, attempt=None):
    root, c = Path(root).resolve(), performance.context(raw)
    if action == "register":
        return register(root, c.RAW)
    if action == "status":
        return previous.read(c.RAW / "control/status.json")
    plan = protocol(root, c.RAW)
    if action == "worker":
        item = p.checked(p.read_json(job), "cross_market_evaluation_work_unit")
        if item["work_kind"] == "generate":
            require(
                os.environ.get("CUDA_VISIBLE_DEVICES")
                in plan["gpu_allocation"]["allowed_gpu_uuids"],
                "generation_worker_on_explicitly_retained_GPU_only",
            )
        original = c.read_protocol(root)
        cap = original["scheduling"][
            "generation_attempts_per_shard"
            if item["work_kind"] == "generate"
            else "scoring_attempts_per_cohort"
        ]
        require(
            type(attempt) is int and 0 < attempt <= attempt_cap(item, cap, plan["target_job_id"]),
            "bounded_worker_attempt",
        )
        return performance.execute(action, root, c.RAW, job, attempt)
    namespace = controller_namespace(
        plan, performance.protocol(root, c.RAW), recovery.protocol(root, c.RAW)
    )
    return namespace[action](root, c.RAW)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "coordinate", "worker", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--raw", type=Path, default=previous.RAW)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    value = execute(args.action, args.root, args.raw, args.job, args.attempt)
    if args.action == "worker":
        return value
    if value is not None:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
