"""Bounded saved-point numerical/repeat audit; never generates or rescores text."""

# ruff: noqa: E501 -- explicit bounded accounting and lineage
import argparse
import gc
import gzip
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

import fixed_kernel_proxy_direction_20260919 as direction
import fixed_kernel_proxy_inputs_20260919 as inputs
import fixed_kernel_proxy_numeric_20260919 as numeric
import numpy as np
import run_fixed_kernel_anchored_training_20260916 as old
import torch
from safetensors.torch import load_file, save_file
from torch.nn.attention import SDPBackend, sdpa_kernel

p, classes = old.p, old.classes
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_proxy_audit_20260919.py"
SOURCES = sorted(
    set(
        old.SOURCES
        + [
            SCRIPT,
            "trusted_data_synthesis/scripts/fixed_kernel_proxy_inputs_20260919.py",
            "trusted_data_synthesis/scripts/fixed_kernel_proxy_numeric_20260919.py",
            "trusted_data_synthesis/scripts/fixed_kernel_proxy_direction_20260919.py",
        ]
    )
)


def worker(root, key):
    root = Path(root).resolve()
    plan = p.checked(p.read_json(root / inputs.OUTPUT / "plan.json"), "anchored_proxy_audit_plan")
    for path, digest in plan["sources"].items():
        p.require(p.sha(root / path) == digest, "proxy.frozen_loaded_code")
    job = next(row for row in plan["jobs"] if row["key"] == key)
    out = root / inputs.OUTPUT / "jobs" / key
    p.write_once(
        out / "started.json", p.record("proxy_job_started", key=key, at=p.now(), pid=os.getpid())
    )
    started, stage = time.monotonic(), "load_exact_saved_real_point"
    try:
        torch.set_num_threads(4)
        parent = p.read_json(root / inputs.PARENT / "plan.json")
        binding = p.read_json(root / inputs.BASE / "material_binding/A.json")
        info, blocks, context = inputs.vectors(root, job["relative"])
        names = [b["name"] for b in blocks]
        model, _ = old.trajectory_training.load_registered_student(
            parent["assets"]["base_binding"], job["seed"], trainable=True
        )
        parameters = {n: v for n, v in model.named_parameters() if v.requires_grad}
        p.require(list(parameters) == names, "proxy.exact_class_coordinate_order")
        with torch.no_grad():
            for b in blocks:
                parameters[b["name"]].copy_(
                    context["theta"][b["start"] : b["stop"]].reshape(b["shape"]).to("cuda:0")
                )
        cache_root = root / parent["trajectory_cache"]["cache_root"]
        cache = old.trajectory_materials.load_pool(
            cache_root, p.read_json(cache_root / "manifest.json"), "A"
        )
        classes.admit(cache, binding)
        stage = "registered_extra_full_class_pass"
        with (out / "class_gradient_events.jsonl").open("xb") as stream:

            def event(value):
                stream.write(p.encode(dict(at=p.now(), **value)) + b"\n")
                if value["completed_packages"] % 25 == 0:
                    stream.flush()

            population = classes._compute(model, cache, info["pi"], binding["mu"], event_sink=event)
        p.require(list(population.names) == names, "proxy.class_columns_match_saved_parameters")
        recomputed_G = torch.cat([population.G[name].detach().cpu().reshape(-1) for name in names])
        p.require(
            torch.allclose(recomputed_G, context["G"], atol=1e-6, rtol=1e-5),
            "proxy.same_point_original_G_reproduced",
        )
        cache_dir = inputs.CACHE / "jobs" / key
        cache_dir.mkdir(parents=True, exist_ok=True)
        matrix_path = cache_dir / "class_gradients.npy"
        p.require(not matrix_path.exists(), "proxy.no_class_matrix_overwrite")
        np.save(matrix_path, population.matrix.numpy(), allow_pickle=False)
        p.write_once(
            out / "class_matrix.json",
            p.record(
                "proxy_extra_class_matrix",
                path=str(matrix_path),
                bytes=matrix_path.stat().st_size,
                sha256=p.sha(matrix_path),
                keys=population.keys,
                names=names,
                accounting=population.accounting,
                G_comparison=numeric.compare(recomputed_G, context["G"]),
            ),
        )
        stage = "numeric_C_and_pi_projection"
        effects, geometries = {}, {}
        for alias in job["aliases"]:
            source = root / alias["relative"]
            alias_info = p.read_json(source / "full_G.json")
            a_blob = load_file(str(source / "G_gJ_a.safetensors"), device="cpu")
            alias_context = {"a": torch.cat([a_blob[f"a/{name}"].reshape(-1) for name in names])}
            reference = load_file(alias["reference_path"], device="cpu")["a_reference"]
            effect, geometry = direction.numerical_effect(
                population.matrix,
                alias_context,
                population.keys,
                alias_info["pi"],
                binding["prior"],
                binding["mu"],
                binding["control_tasks"],
                alias["run"]["condition"],
                p.read_json(source / "C.json")["C"],
                p.read_json(source / "distribution_update.json")["pi_next"],
                reference,
                plan["numeric_limits"],
            )
            effects[alias["key"]], geometries[alias["key"]] = effect, geometry
        passed = all(row["passed"] for row in effects.values())
        p.write_once(
            out / "numeric_projection.json",
            p.record(
                "proxy_numeric_projection", effects=effects, all_aliases_passed=passed, at=p.now()
            ),
        )
        if not passed:
            p.write_once(
                out / "report.json",
                p.record(
                    "proxy_job_report",
                    key=key,
                    status="MATERIAL_NUMERIC_CHANGE_NO_DELAYED_RELEASE",
                    numeric_passed=False,
                    effects=effects,
                    extra_class_passes=1,
                    extra_class_sequence_tokens=population.accounting["sequence_tokens"],
                    replayed_trajectories=0,
                    replayed_output_tokens=0,
                    generated_sessions=0,
                    scored_sessions=0,
                    elapsed_seconds=time.monotonic() - started,
                    at=p.now(),
                ),
            )
            return
        stage = "one_same_token_replay_per_positive"
        state = load_file(
            str(root / job["point"]["adapter_directory"] / "adapter.safetensors"), device="cpu"
        )
        p.require(
            set(state) == set(names)
            and inputs.tensor_digest(state) == job["point"]["parameter_digest"],
            "proxy.exact_saved_virtual_adapter",
        )
        theta = {name: state[name].to("cuda:0").requires_grad_(True) for name in names}
        gradients = torch.empty((len(job["positive"]), context["G"].numel()), dtype=torch.float64)
        replay_total = torch.zeros_like(context["gJ"], device="cuda:0")
        responses = tokens = positions = 0
        with (out / "replay_events.jsonl").open("xb") as stream:
            for i, item in enumerate(job["positive"]):
                packed = Path(item["path"]).read_bytes()
                p.require(
                    len(packed) == item["bytes"] and p.sha(packed) == item["sha256"],
                    "proxy.admitted_positive_token_cache",
                )
                content = json.loads(gzip.decompress(packed))
                p.require(
                    content["parameter_digest"] == job["point"]["parameter_digest"],
                    "proxy.same_parameter_point_for_replay",
                )
                value = torch.zeros(context["G"].numel(), dtype=torch.float64)
                for response_index, turn in enumerate(content["turns"]):
                    with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                        _, gradient, used = old.feedback.segmented.segmented_logp(
                            model,
                            theta,
                            turn["prompt"],
                            turn["tokens"],
                            expected=turn["logps"],
                            block_size=8,
                        )
                    flat = torch.cat([gradient[name].reshape(-1) for name in names])
                    replay_total.add_(flat, alpha=1 / 360)
                    value.add_(flat.detach().cpu().double())
                    tokens += len(turn["tokens"])
                    responses += 1
                    positions += used["cached_forward_target_positions"]
                    stream.write(
                        p.encode(
                            dict(
                                event="saved_positive_response_replayed",
                                completed_trajectories=i,
                                total_trajectories=len(job["positive"]),
                                trajectory=item["index"],
                                response=response_index,
                                responses=responses,
                                sampled_output_tokens=tokens,
                                at=p.now(),
                            )
                        )
                        + b"\n"
                    )
                    stream.flush()
                    del gradient, flat
                gradients[i] = value
                dest = cache_dir / "positive_gradients" / f"{item['index']:04d}.safetensors"
                dest.parent.mkdir(parents=True, exist_ok=True)
                p.require(not dest.exists(), "proxy.no_positive_gradient_overwrite")
                save_file({"log_probability_gradient_sum": value}, str(dest))
        comparison = numeric.compare(replay_total.cpu(), context["gJ"])
        p.require(
            torch.allclose(replay_total.cpu(), context["gJ"], atol=1e-6, rtol=1e-5),
            "proxy.existing_total_gJ_reproduced",
        )
        del theta, model, replay_total, state
        gc.collect()
        torch.cuda.empty_cache()
        stage = "CPU_shared_projections_repeat_and_deletion"
        covectors = direction.item_covectors(
            context,
            gradients,
            blocks,
            info["optimizer_snapshot"]["groups"],
            info["optimizer_snapshot"]["clip"],
        )
        torch.set_num_threads(16)
        dots = direction.project(population.matrix, covectors, population.keys)
        np.save(cache_dir / "positive_state_dot_products.npy", dots, allow_pickle=False)
        results = {}
        for alias in job["aliases"]:
            geometry = geometries[alias["key"]]
            result = direction.repeat_analysis(
                geometry.centered(dots), job["positive"], geometry, alias["run"]["condition"]
            )
            p.write_once(
                out / (alias["key"] + "_direction.json"),
                p.record("proxy_repeat_direction", source_point=alias, **result),
            )
            results[alias["key"]] = {
                name: value for name, value in result.items() if name != "leave_one_positive_out"
            }
        p.write_once(
            out / "report.json",
            p.record(
                "proxy_job_report",
                key=key,
                status="COMPLETE_SCOPED_NUMERIC_AND_DIRECTION",
                numeric_passed=True,
                effects=effects,
                directions=results,
                total_gJ_replay_comparison=comparison,
                extra_class_passes=1,
                extra_class_sequence_tokens=population.accounting["sequence_tokens"],
                replayed_trajectories=len(job["positive"]),
                replayed_responses=responses,
                replayed_output_tokens=tokens,
                cached_forward_target_positions=positions,
                generated_sessions=0,
                scored_sessions=0,
                elapsed_seconds=time.monotonic() - started,
                at=p.now(),
            ),
        )
    except Exception as failure:
        p.write_once(
            out / "failure.json",
            p.record(
                "proxy_job_failure",
                key=key,
                stage=stage,
                error=repr(failure),
                traceback=traceback.format_exc(),
                at=p.now(),
                retries=0,
            ),
        )
        raise


def publish(root, output, key, summary, explanation):
    """Only bounded aggregate summaries/documents, never raw matrices or sessions."""
    root = Path(root).resolve()
    public = root / output / "public"
    attempt = public / (key + "_publication.json")
    if attempt.exists():
        return
    forbidden = {
        "prompt",
        "tokens",
        "logps",
        "theta",
        "first_moment",
        "second_moment",
        "gJ",
        "a",
        "pi_next",
        "positive",
        "leave_one_positive_out",
    }

    def check(value):
        if isinstance(value, dict):
            p.require(not forbidden.intersection(value), "proxy.public_summary_no_raw_payload")
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            p.require(len(value) <= 16, "proxy.public_small_aggregate_list")
            for child in value:
                check(child)

    check(summary)
    p.require(len(p.encode(summary)) < 65536, "proxy.small_public_summary")
    path = public / (key + ".json")
    doc = root / "trusted_data_synthesis/docs/proxy_audit_20260919" / (key + ".md")
    try:
        p.write_once(path, summary)
        doc.parent.mkdir(parents=True, exist_ok=True)
        with doc.open("x") as stream:
            stream.write(
                "# 审计后实验阶段记录\n\n"
                + explanation
                + "\n\n公开文件不含原始会话、模型、梯度或逐轨迹数据。实际新增调用以本阶段计量为准。\n\n```json\n"
                + json.dumps(summary, ensure_ascii=False, indent=2)
                + "\n```\n"
            )
        paths = [str(path.relative_to(root)), str(doc.relative_to(root))]
        subprocess.run(["git", "add", "--sparse", "-f", "--", *paths], cwd=root, check=True)
        subprocess.run(
            [
                "git",
                "commit",
                "--only",
                "-m",
                "Record bounded audit successor " + key,
                "--",
                *paths,
            ],
            cwd=root,
            check=True,
        )
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        subprocess.run(
            [
                "git",
                "-c",
                "http.proxy=",
                "push",
                "https://github.com/haoyueliuzhao/Data-Synthesis.git",
                "HEAD:main",
            ],
            cwd=root,
            check=True,
        )
        state = dict(status="PUBLISHED", commit=commit)
    except Exception as failure:
        state = dict(status="PUBLICATION_FAILED_NO_SCIENTIFIC_RETRY", error=repr(failure))
    p.write_once(attempt, p.record("proxy_publication_attempt", **state, at=p.now()))


def coordinate(root):
    root = Path(root).resolve()
    out = root / inputs.OUTPUT
    plan = p.checked(p.read_json(out / "plan.json"), "anchored_proxy_audit_plan")
    p.write_once(
        out / "coordinator_started.json",
        p.record("proxy_coordinator_started", pid=os.getpid(), at=p.now()),
    )
    old.OUTPUT = inputs.OUTPUT
    active, cursor = [], 0
    try:
        while cursor < len(plan["jobs"]) or active:
            for process, lease, stream, key in list(active):
                if process.poll() is not None:
                    p.require(
                        process.returncode == 0, "proxy.job_failure_no_automatic_retry:" + key
                    )
                    lease.close()
                    stream.close()
                    active.remove((process, lease, stream, key))
            if (
                cursor < len(plan["jobs"])
                and len(active) < plan["maximum_workers"]
                and old.host_memory()["MemAvailable_bytes"] >= plan["minimum_host_available_bytes"]
            ):
                candidates = old.claim_gpus(root, maximum=1)
                if candidates:
                    gpu, lease = candidates[0]
                    key = plan["jobs"][cursor]["key"]
                    stream = (out / (key + ".log")).open("x")
                    env = dict(
                        os.environ,
                        CUDA_VISIBLE_DEVICES=gpu["uuid"],
                        CUBLAS_WORKSPACE_CONFIG=":4096:8",
                        OMP_NUM_THREADS="4",
                        OPENBLAS_NUM_THREADS="4",
                        MKL_NUM_THREADS="4",
                        TOKENIZERS_PARALLELISM="false",
                    )
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            str(root / SCRIPT),
                            "--root",
                            str(root),
                            "--mode",
                            "worker",
                            "--job",
                            key,
                        ],
                        cwd=root,
                        env=env,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        pass_fds=(lease.fileno(),),
                        start_new_session=True,
                    )
                    active.append((process, lease, stream, key))
                    p.write_once(
                        out / "launches" / (key + ".json"),
                        p.record("proxy_job_launch", key=key, gpu=gpu, pid=process.pid, at=p.now()),
                    )
                    cursor += 1
            if cursor < len(plan["jobs"]) or active:
                time.sleep(20)
        jobs = [p.read_json(out / "jobs" / job["key"] / "report.json") for job in plan["jobs"]]
        numeric_passed = all(job["numeric_passed"] for job in jobs)
        points = []
        for job in jobs:
            for key, effect in job["effects"].items():
                result = job.get("directions", {}).get(key)
                points.append(
                    dict(
                        key=key,
                        numeric_passed=effect["passed"],
                        C_relative_weighted_RMS=effect["stable_vs_saved_C"][
                            "relative_weighted_RMS"
                        ],
                        pi_reference_TV=effect["stable_vs_saved_next_pi_weighted_TV"],
                        cross=result["cross"] if result else None,
                        leave_one_out=result["leave_one_out_summary"] if result else None,
                    )
                )
        p.require(len(points) == 12, "proxy.all_registered_points_accounted")
        totals = {
            name: sum(job.get(name, 0) for job in jobs)
            for name in (
                "extra_class_passes",
                "extra_class_sequence_tokens",
                "replayed_trajectories",
                "replayed_responses",
                "replayed_output_tokens",
                "cached_forward_target_positions",
            )
        }
        p.require(
            totals["extra_class_passes"] <= 12
            and totals["replayed_trajectories"] <= 652
            and totals["replayed_output_tokens"] <= 166346,
            "proxy.registered_extra_resource_caps",
        )
        report = p.record(
            "anchored_proxy_audit_report",
            plan_id=plan["id"],
            status="PASS_AS_SCOPED_READY_FOR_DELAYED_C"
            if numeric_passed
            else "BLOCKED_MATERIAL_NUMERIC_CHANGE",
            all_twelve_numeric_points_passed=numeric_passed,
            direction_audit_completed=numeric_passed,
            direction_stability_not_assumed=True,
            points=points,
            actual_extra_resources=totals,
            new_generated_sessions=0,
            new_financial_scores=0,
            B_and_confirmation=0,
            at=p.now(),
        )
        p.write_once(out / "report.json", report)
        publish(
            root,
            inputs.OUTPUT,
            "complete_proxy_audit",
            report,
            "原负结果保留；数值门通过才准入已登记Delayed-C。repeat交叉分数是同固定点Monte Carlo诊断，不是独立泛化或已取得训练收益。",
        )
    except Exception as failure:
        for process, _, _, _ in active:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        p.write_once(
            out / "coordinator_failure.json",
            p.record(
                "proxy_coordinator_failure",
                error=repr(failure),
                traceback=traceback.format_exc(),
                at=p.now(),
                no_training_authorized_by_failure=True,
            ),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("prepare", "coordinate", "worker"), required=True)
    parser.add_argument("--job")
    args = parser.parse_args()
    if args.mode == "prepare":
        torch.set_num_threads(4)
        inputs.prepare(args.root, SOURCES)
    elif args.mode == "worker":
        worker(args.root, args.job)
    else:
        coordinate(args.root)
