"""Independent original-Base FinQA dev883 baseline for the fixed five-arm mainline.

No adapter, material admission, training, API request, GPU reservation or process
killing. Two fixed public-only shards generate before the full-cohort score gate.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from .calibration import (
    CACHE,
    ROOT,
    gpu_inventory,
    now,
    publish,
    status,
)
from .calibration import (
    identity as process_identity,
)
from .contracts import Episode, ModelIdentity, PrivateReference, RunConfig, TaskBundle, digest
from .harness import episode_tool_specs, system_message
from .planning import task_key, verify_role_plan
from .providers import LocalTorchProvider, tokenizer_binding
from .settlement import episode_is_complete
from .storage import (
    UnsettledExecution,
    _read_snapshot_rows,
    execute_run,
    load_public_snapshot,
    prepare_run,
    read_json,
    runtime_binding,
    runtime_task_view,
    sealed_episodes,
)
from .v6_task import score_public_reasoning_program

ORIGIN = CACHE / "finqa_v6_01/experiment0_01/protocol.json"
OUTPUT = CACHE / "finqa_five_arm_mainline_20260929/base_dev883_01"
DESIGN = ROOT / "trusted_data_synthesis/docs/finqa_v6_five_arm_protocol_20260928.md"
ALLOWED_GPU_INDICES = (0, 7)
MINIMUM_FREE_MIB = 24576


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bound(value):
    return {**value, "id": digest(value)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def persist(directory, value, name="record.json"):
    path = Path(directory) / name
    if path.exists():
        require(read_json(path) == value, "immutable baseline evidence changed: " + str(path))
    else:
        publish(directory, value, name)


def evaluation_config():
    return RunConfig(
        harness_id="bigfinance-derived-vtdo-v7",
        submission_profile="finqa-public-reasoning-v2",
        role="development",
        tier="EVAL_NATIVE",
        local_tool_protocol="qwen2.5-native-tool-call-v1",
        seed=20260928,
        temperature=0,
        top_p=1,
        top_k=0,
        max_steps=32,
        max_new_tokens=2048,
        context_limit=24576,
    )


def fixed_shards(task_keys):
    require(len(task_keys) == len(set(task_keys)) == 883, "complete original dev883 required")
    return [
        dict(key="dev00", task_keys=list(task_keys[:442])),
        dict(key="dev01", task_keys=list(task_keys[442:])),
    ]


def load_tokenizer(assets):
    from transformers import AutoTokenizer

    base, binding = assets["base_binding"], assets["tokenizer_binding"]
    directory = Path(base["directory"])
    require(directory == Path(binding["directory"]), "base/tokenizer directories differ")
    # Original weight hashes stay bound. The retained model loader verifies their
    # actual bytes once per loading process; registration only checks the manifest.
    for member in base["members"]:
        path = directory / member["path"]
        require(
            path.is_file() and not path.is_symlink() and path.stat().st_size == member["bytes"],
            "bound original base checkpoint member missing or resized",
        )
    for member in binding["members"]:
        path = directory / member["relative_path"]
        require(
            path.stat().st_size == member["byte_count"] and sha(path) == member["sha256"],
            "original tokenizer bytes changed",
        )
    tokenizer = AutoTokenizer.from_pretrained(
        directory, local_files_only=True, trust_remote_code=False
    )
    require(
        tokenizer.chat_template == binding["chat_template"]
        and tokenizer.eos_token_id == binding["eos_token_id"],
        "original tokenizer template/EOS changed",
    )
    return tokenizer


def base_identity(assets, tokenizer):
    tokens, template = tokenizer_binding(tokenizer)
    binding = assets["base_binding"]
    return ModelIdentity(
        backend="local_torch",
        model_id=binding["id"],
        point_id="original-base-no-adapter:" + binding["id"],
        parameter_digest=None,
        tokenizer_digest=tokens,
        chat_template_digest=template,
    )


def build_plan(source_commit):
    previous = read_json(ORIGIN)
    require(
        previous["id"] == digest({k: v for k, v in previous.items() if k != "id"}),
        "original role/model source protocol changed",
    )
    manifest, tasks, lineages = load_public_snapshot(previous["snapshot"])
    require(manifest["id"] == previous["snapshot_id"], "original QA snapshot changed")
    verify_role_plan(previous["role_plan"], tasks, lineages)
    chosen = [
        (task, lineage)
        for task, lineage in zip(tasks, lineages, strict=True)
        if previous["role_plan"]["assignments"][task_key(task)] == "development"
    ]
    require(
        all(t.dataset == "finqa" and lineage.original_split == "dev" for t, lineage in chosen),
        "Base evaluation is original official FinQA dev only",
    )
    keys = [task_key(task) for task, _ in chosen]
    shards = fixed_shards(keys)
    tokenizer = load_tokenizer(previous["assets"])
    config = evaluation_config()
    return bound(
        dict(
            schema="finqa_five_arm_base_dev883.v1",
            at=now(),
            source_commit=source_commit,
            runtime_binding=runtime_binding(),
            parent_protocol_id=previous["id"],
            design_path=str(DESIGN),
            design_sha256=sha(DESIGN),
            snapshot=previous["snapshot"],
            snapshot_id=manifest["id"],
            role_plan=previous["role_plan"],
            assets=previous["assets"],
            config=config.model_dump(mode="json"),
            model_identity=base_identity(previous["assets"], tokenizer).model_dump(mode="json"),
            tasks=keys,
            shards=shards,
            denominator=883,
            maximum_generation_calls=883 * 32,
            public_view_sha256={
                task_key(t): digest(runtime_task_view(t, config)) for t, _ in chosen
            },
            public_system=system_message(config),
            public_tools=episode_tool_specs(config),
            model="original Qwen2.5-7B-Instruct",
            adapter=None,
            original_weight_hash_binding=True,
            parameter_delta_hash_claimed=False,
            no_training_or_material_dependency=True,
            configuration_choice=(
                "prospectively instantiate original five-arm greedy dev design with "
                "V7 public program profile; no different exact dev configuration "
                "existed in experiment0"
            ),
            future_fifteen_models_require_same_evaluation_configuration=True,
            base_results_not_for_prompt_collection_or_qualification_tuning=True,
            all_883_generation_before_any_reference_scoring=True,
            scoring="v6_task.score_public_reasoning_program",
            legacy_score_run_not_used=(
                "legacy numeric Final scorer rejects program-only final_answer=None"
            ),
            no_failed_episode_retry=True,
            no_partial_success_denominator=True,
            process_attempts_per_shard=3,
            automatic_retry_only_for_preload_resource_wait=True,
            interrupted_or_unknown_model_call="retain intent/raw evidence and stop; never resample",
            resource_policy=dict(
                allowed_gpu_indices=list(ALLOWED_GPU_INDICES),
                minimum_free_MiB=MINIMUM_FREE_MIB,
                shared_GPU_allowed=True,
                utilization_or_foreign_PID_rejection=False,
                reservation_holders=False,
                kill_other_processes=False,
            ),
            scoring_does_not_claim_trace_CompletePass=True,
            API_calls=0,
            training_started=False,
        )
    )


def checked_plan(output):
    plan = read_json(Path(output) / "protocol.json")
    require(
        plan["id"] == digest({k: v for k, v in plan.items() if k != "id"}), "Base protocol changed"
    )
    require(plan["runtime_binding"] == runtime_binding(), "frozen Base runtime changed")
    return plan


def shard_root(output, shard):
    return Path(output) / "shards" / shard["key"] / "generation"


def register(output=OUTPUT):
    output = Path(output)
    if (output / "protocol.json").exists():
        plan = checked_plan(output)
        require(
            all((shard_root(output, shard) / "run.json").exists() for shard in plan["shards"]),
            "partial Base registration needs inspection, not overwrite",
        )
        return plan
    require(not output.exists(), "partial Base registration needs inspection, not overwrite")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", head + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "commit frozen source before Base registration",
        )
    plan = build_plan(head)
    publish(output, plan, "protocol.json")
    for shard in plan["shards"]:
        prepare_run(
            plan["snapshot"],
            plan["role_plan"],
            shard_root(output, shard),
            role="development",
            config=RunConfig.model_validate(plan["config"]),
            identity=ModelIdentity.model_validate(plan["model_identity"]),
            task_keys=shard["task_keys"],
        )
    return plan


def inspect_shard(output, plan, shard):
    root = shard_root(output, shard)
    run = read_json(root / "run.json")
    require(
        run["id"] == digest({k: v for k, v in run.items() if k != "id"})
        and run["runtime_binding"] == plan["runtime_binding"]
        and run["tasks"] == shard["task_keys"]
        and run["provider"] == plan["model_identity"]
        and run["config"] == plan["config"]
        and run["snapshot_id"] == plan["snapshot_id"],
        "shard registration differs from original Base plan",
    )
    finished = 0
    for key, eid in zip(run["tasks"], run["episode_keys"], strict=True):
        episode_path, events = root / "episodes" / eid / "episode.json", root / "events" / eid
        if not episode_path.exists():
            if events.exists():
                raise UnsettledExecution(
                    "durable episode intent without completed raw episode: " + key
                )
            continue
        episode = Episode.model_validate_json(episode_path.read_bytes())
        require(
            episode_is_complete(episode),
            "unknown/infrastructure episode must not be retried or scored",
        )
        require(
            episode.config.model_dump(mode="json") == plan["config"]
            and episode.provider.model_dump(mode="json") == plan["model_identity"]
            and task_key(episode) == key
            and episode.public_task_sha256 == run["public_view_sha256"][key],
            "saved original episode identity changed",
        )
        recorded = sorted(events.glob("*/event.json"))
        completion = read_json(recorded[-1]) if recorded else {}
        require(
            completion.get("kind") == "episode_completed"
            and completion.get("payload") == episode.model_dump(mode="json"),
            "saved original episode does not match durable completion",
        )
        finished += 1
    sealed = (root / "generation_seal/seal.json").exists()
    if sealed:
        sealed_episodes(root)
        require(finished == len(shard["task_keys"]), "shard seal lacks original tasks")
    return dict(completed=finished, denominator=len(shard["task_keys"]), sealed=sealed)


def seal_all(output, plan):
    records, episodes, seen = [], [], []
    for shard in plan["shards"]:
        progress = inspect_shard(output, plan, shard)
        require(progress["sealed"], "all registered shards must seal before private scoring")
        run, seal, values = sealed_episodes(shard_root(output, shard))
        records.append(
            dict(
                shard=shard["key"],
                run_id=run["id"],
                seal_id=seal["id"],
                seal_sha256=sha(shard_root(output, shard) / "generation_seal/seal.json"),
            )
        )
        seen.extend(run["tasks"])
        episodes.extend(values)
    require(
        seen == plan["tasks"] and len(episodes) == plan["denominator"],
        "global generation seal must retain the exact whole dev cohort",
    )
    seal = bound(
        dict(
            schema="finqa_base_whole_dev_generation.v1",
            protocol_id=plan["id"],
            denominator=plan["denominator"],
            shards=records,
            episode_sha256=[digest(e) for e in episodes],
            private_references_read=False,
            all_generation_complete=True,
            all_provider_calls_settled=True,
        )
    )
    persist(Path(output) / "generation_seal", seal)
    return seal, episodes


def score_all(output, plan):
    seal, episodes = seal_all(output, plan)  # No private file opened above this barrier.
    manifest, tasks, lineages = load_public_snapshot(plan["snapshot"])
    require(manifest["id"] == plan["snapshot_id"], "score source snapshot changed")
    references = _read_snapshot_rows(
        plan["snapshot"], "private.references.jsonl", PrivateReference, manifest
    )
    wanted = set(plan["tasks"])
    bundles = {
        task_key(t): TaskBundle(public=t, reference=r, lineage=lineage)
        for t, r, lineage in zip(tasks, references, lineages, strict=True)
        if task_key(t) in wanted
    }
    results = [
        dict(
            task_key=key,
            native=score_public_reasoning_program(bundles[key], episode),
            stop_reason=episode.stop_reason,
            actual_model_calls=episode.actual_model_calls,
            tool_calls=len(episode.tool_events),
            tool_errors=sum(event.is_error for event in episode.tool_events),
        )
        for key, episode in zip(plan["tasks"], episodes, strict=True)
    ]
    metrics = {}
    for name in ("execution_accuracy", "program_accuracy"):
        values = [r["native"]["native"][name] for r in results]
        known = [v for v in values if type(v) in (int, float)]
        metrics[name] = dict(
            denominator=len(values),
            scored=len(known),
            unknown=len(values) - len(known),
            mean_over_scored=sum(known) / len(known) if known else None,
            complete_dataset_mean=sum(known) / len(values) if len(known) == len(values) else None,
        )
    report = bound(
        dict(
            schema="finqa_five_arm_base_dev_report.v1",
            protocol_id=plan["id"],
            generation_seal_id=seal["id"],
            denominator=plan["denominator"],
            metrics=metrics,
            native_status_counts=dict(Counter(r["native"]["status"] for r in results)),
            results=results,
            original_base_no_adapter=True,
            trained_Student_count=0,
            training_value_confirmed=False,
            trajectory_CompletePass_claimed=False,
            automatic_other_arm_launch=False,
        )
    )
    persist(Path(output) / "scores", report)
    return report


def eligible_gpus(rows, used=()):
    return sorted(
        (
            row
            for row in rows
            if row["index"] in ALLOWED_GPU_INDICES
            and row["free"] >= MINIMUM_FREE_MIB
            and row["uuid"] not in set(used)
        ),
        key=lambda row: (-row["free"], row["index"]),
    )


def load_provider(plan):
    from ..experiments.finance_qa_vnext_pq_student import model as retained

    model, scope = retained.load_student(plan["assets"]["base_binding"], 20260928, trainable=False)
    require(
        scope is None
        and not any(".lora_" in name for name, _ in model.named_parameters())
        and not any(p.requires_grad for p in model.parameters()),
        "Base must have no adapter or trainables",
    )
    tokenizer = load_tokenizer(plan["assets"])
    identity = base_identity(plan["assets"], tokenizer)
    require(
        identity.model_dump(mode="json") == plan["model_identity"], "original Base identity changed"
    )
    return LocalTorchProvider(model, tokenizer, identity)


def worker(output, key, gpu, attempt):
    output = Path(output)
    plan = checked_plan(output)
    shard = next(j for j in plan["shards"] if j["key"] == key)
    require(1 <= attempt <= plan["process_attempts_per_shard"], "finite worker process budget")
    directory = output / "shards" / key / "attempts" / f"{attempt:02d}"
    publish(
        directory / "started",
        dict(
            pid=os.getpid(),
            process_identity=process_identity(os.getpid()),
            gpu=gpu,
            at=now(),
            shard=key,
            attempt=attempt,
        ),
    )
    outcome = None
    try:
        progress = inspect_shard(output, plan, shard)
        if progress["sealed"]:
            outcome = dict(status="COMPLETE", resumed_read_only=True)
        elif not any(row["uuid"] == gpu for row in eligible_gpus(gpu_inventory())):
            outcome = dict(status="RESOURCE_WAIT", no_model_loaded=True, no_model_calls=True)
        else:
            os.environ["CUDA_VISIBLE_DEVICES"] = gpu
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
            provider = load_provider(plan)
            seal = asyncio.run(execute_run(shard_root(output, shard), provider))
            outcome = dict(status="COMPLETE", generation_seal_id=seal["id"])
    except BaseException as error:
        outcome = dict(
            status="BLOCKED",
            exception_type=type(error).__name__,
            reason=str(error),
            failed_episode_retry_allowed=False,
        )
    persist(directory / "outcome", {**outcome, "at": now()})
    return (
        0 if outcome["status"] == "COMPLETE" else 75 if outcome["status"] == "RESOURCE_WAIT" else 1
    )


def latest_worker(output, key):
    attempts = sorted((Path(output) / "shards" / key / "attempts").glob("*"))
    if not attempts:
        return None
    directory = attempts[-1]
    start = directory / "started/record.json"
    launched = directory / "launched/record.json"
    process = read_json(start if start.exists() else launched)
    outcome = (
        read_json(directory / "outcome/record.json")
        if (directory / "outcome/record.json").exists()
        else None
    )
    return dict(
        attempt=int(directory.name),
        process=process,
        outcome=outcome,
        alive=bool(process["process_identity"])
        and process_identity(process["pid"]) == process["process_identity"],
    )


def launch_worker(output, shard, gpu, attempt):
    output = Path(output)
    directory = output / "shards" / shard["key"] / "attempts" / f"{attempt:02d}"
    log_path = output / "logs" / f"{shard['key']}_{attempt:02d}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    environment = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": gpu["uuid"],
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "1",
    }
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                __spec__.name,
                "worker",
                "--output",
                str(output),
                "--key",
                shard["key"],
                "--gpu",
                gpu["uuid"],
                "--attempt",
                str(attempt),
            ],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    publish(
        directory / "launched",
        dict(
            pid=process.pid,
            process_identity=process_identity(process.pid),
            gpu=gpu["uuid"],
            gpu_index=gpu["index"],
            at=now(),
            shard=shard["key"],
            attempt=attempt,
        ),
    )


def controller(output, *, poll_seconds=15):
    output = Path(output)
    plan = checked_plan(output)
    with (output / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            progress, workers = {}, {}
            try:
                for shard in plan["shards"]:
                    state = latest_worker(output, shard["key"])
                    workers[shard["key"]] = state
                    if not state or not state["alive"]:
                        progress[shard["key"]] = inspect_shard(output, plan, shard)
                        if state and not progress[shard["key"]]["sealed"]:
                            require(
                                state["outcome"] and state["outcome"]["status"] == "RESOURCE_WAIT",
                                "worker stopped or failed; no automatic generation retry",
                            )
                    else:
                        progress[shard["key"]] = dict(
                            status="RUNNING",
                            saved_episode_files=sum(
                                1
                                for _ in (shard_root(output, shard) / "episodes").glob(
                                    "*/episode.json"
                                )
                            ),
                            denominator=len(shard["task_keys"]),
                            file_count_is_progress_only_not_admission=True,
                        )
                if all(p.get("sealed") for p in progress.values()):
                    report = score_all(output, plan)
                    status(
                        output,
                        dict(
                            at=now(),
                            phase="COMPLETE",
                            protocol_id=plan["id"],
                            denominator=883,
                            scores_id=report["id"],
                            workers_exited=True,
                            training_started=False,
                            API_calls=0,
                        ),
                    )
                    return report
                active = [s["process"]["gpu"] for s in workers.values() if s and s["alive"]]
                available = eligible_gpus(gpu_inventory(), active)
                for shard in plan["shards"]:
                    if (
                        progress[shard["key"]].get("sealed")
                        or progress[shard["key"]].get("status") == "RUNNING"
                    ):
                        continue
                    state = workers[shard["key"]]
                    attempt = state["attempt"] + 1 if state else 1
                    require(
                        attempt <= plan["process_attempts_per_shard"],
                        "preload resource-wait attempts exhausted",
                    )
                    if available:
                        launch_worker(output, shard, available.pop(0), attempt)
                status(
                    output,
                    dict(
                        at=now(),
                        phase="GENERATING_OR_WAITING_RESOURCE",
                        protocol_id=plan["id"],
                        denominator=883,
                        shards=progress,
                        API_calls=0,
                        training_started=False,
                    ),
                )
            except Exception as error:
                status(
                    output,
                    dict(
                        at=now(),
                        phase="BLOCKED",
                        protocol_id=plan["id"],
                        exception_type=type(error).__name__,
                        reason=str(error),
                        no_resampling=True,
                        denominator=883,
                        training_started=False,
                        API_calls=0,
                    ),
                )
                raise
            time.sleep(poll_seconds)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "start", "run", "worker", "status"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--key", choices=["dev00", "dev01"])
    parser.add_argument("--gpu")
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args(argv)
    if args.action == "register":
        print(dict(protocol_id=register(args.output)["id"]))
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    elif args.action == "run":
        controller(args.output)
    elif args.action == "worker":
        require(args.key and args.gpu and args.attempt, "worker needs shard/GPU/attempt")
        return worker(args.output, args.key, args.gpu, args.attempt)
    else:
        checked_plan(args.output)
        with (args.output / "controller.log").open("ab") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", __spec__.name, "run", "--output", str(args.output)],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print(dict(pid=process.pid, process_identity=process_identity(process.pid), at=now()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
