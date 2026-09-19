"""One saved-artifact admission and numeric inventory for the bounded proxy audit."""

# ruff: noqa: E501 -- explicit frozen evidence and accounting
import gzip
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import fixed_kernel_proxy_numeric_20260919 as numeric
import torch
from safetensors.torch import load_file, save_file

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

BASE = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/anchored_sources_20260916"
PARENT = BASE + "/registered_A"
OUTPUT = BASE + "/proxy_direction_audit_20260919"
CACHE = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/proxy_audit_cache_20260919"
)
AUDIT_SHA = "94f702b7cf2e1b977e30a29abfc88d68225a5e2f7a1f28482efb003f76e4c474"


def tensor_digest(tensors):
    digest = hashlib.sha256()
    for name, value in sorted(tensors.items()):
        digest.update(p.encode([name, str(value.dtype), list(value.shape)]))
        digest.update(value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def vectors(root, relative):
    directory = Path(root) / relative
    info = p.read_json(directory / "full_G.json")
    state = load_file(str(directory / "real_point_and_optimizer.safetensors"), device="cpu")
    data = load_file(str(directory / "G_gJ_a.safetensors"), device="cpu")
    names = [row["name"] for row in info["optimizer_snapshot"]["parameters"]]
    blocks, cursor = [], 0
    for metadata in info["optimizer_snapshot"]["parameters"]:
        name = metadata["name"]
        for field, prefix in (
            ("parameter", "theta"),
            ("first_moment", "first_moment"),
            ("second_moment", "second_moment"),
        ):
            actual = state[f"{prefix}/{name}"]
            expected = metadata[field]
            p.require(
                list(actual.shape) == expected["shape"]
                and str(actual.dtype) == expected["dtype"]
                and p.sha(actual.contiguous().view(torch.uint8).numpy().tobytes())
                == expected["sha256"],
                "proxy.saved_actual_optimizer_tensor",
            )
        size = state[f"theta/{name}"].numel()
        blocks.append(
            dict(
                name=name,
                start=cursor,
                stop=cursor + size,
                shape=list(state[f"theta/{name}"].shape),
                step=metadata["step"],
                group=metadata["group"],
            )
        )
        cursor += size
    named = {
        prefix: {name: data[f"{prefix}/{name}"] for name in names} for prefix in ("G", "gJ", "a")
    }
    p.require(tensor_digest(named["G"]) == info["G_digest"], "proxy.saved_G_digest")
    p.require(
        tensor_digest(named["gJ"]) == p.read_json(directory / "gJ.json")["gJ_digest"],
        "proxy.saved_gJ_digest",
    )
    flat = {
        prefix: torch.cat([named[prefix][name].reshape(-1) for name in names]) for prefix in named
    }
    flat.update(
        {
            prefix: torch.cat([state[f"{prefix}/{name}"].reshape(-1) for name in names])
            for prefix in ("theta", "first_moment", "second_moment")
        }
    )
    return info, blocks, flat


def probability(value):
    from fractions import Fraction

    return float(Fraction(str(value)))


def exposure(binding, updates):
    prior, mu = binding["prior"], binding["mu"]
    methods = {(r["task_id"], r["state_id"]): r["method"] for r in binding["package_mappings"]}
    result = {}
    for run, (one, two) in updates.items():
        prior_mass, effective_mass = Counter(), Counter()
        total_tv = between_tv = within_tv = 0.0
        for task, states in prior.items():
            mass = probability(mu[task])
            base = {z: probability(v) for z, v in states.items()}
            mean = {z: (probability(one[task][z]) + probability(two[task][z])) / 2 for z in states}
            old_methods, new_methods = Counter(), Counter()
            for z in states:
                method = methods[task, z]
                old_methods[method] += base[z]
                new_methods[method] += mean[z]
                prior_mass[method] += mass * base[z]
                effective_mass[method] += mass * mean[z]
                total_tv += mass * abs(mean[z] - base[z]) / 2
            between_tv += mass * sum(abs(new_methods[m] - old_methods[m]) for m in old_methods) / 2
            within_tv += (
                mass
                * sum(
                    abs(
                        mean[z]
                        - new_methods[methods[task, z]] * base[z] / old_methods[methods[task, z]]
                    )
                    for z in states
                )
                / 2
            )
        result[run] = dict(
            prior_method_probability_mass=dict(prior_mass),
            mean_ten_epoch_method_probability_mass=dict(effective_mass),
            delta_method_probability_mass={
                m: effective_mass[m] - prior_mass[m] for m in prior_mass
            },
            effective_pi_to_prior_weighted_TV=total_tv,
            between_method_TV=between_tv,
            within_method_TV_relative_to_prior_conditionals=within_tv,
            TV_components_not_asserted_additive=True,
            five_epochs_each_weight=0.5,
            probability_mass_not_method_success_quality=True,
        )
    return result


def concentration(rows):
    output = {}
    for field in ("task_id", "source_cluster"):
        counts = Counter(row[field] for row in rows)
        total = len(rows)
        shares = [n / total for n in counts.values()] if total else []
        output[field] = dict(
            distinct=len(counts),
            counts=dict(counts),
            maximum_share=max(shares, default=0),
            effective_count=1 / sum(x * x for x in shares) if shares else 0,
        )
    return output


def prepare(root, source_paths):
    root = Path(root).resolve()
    out = root / OUTPUT
    p.require(not (out / "plan.json").exists(), "proxy.one_preparation")
    parent = p.checked(p.read_json(root / PARENT / "plan.json"), "anchored_registered_A_plan")
    completed = p.read_json(root / PARENT / "report.json")
    p.require(completed["status"] == "COMPLETE_SIX_NEW_A_RUNS", "proxy.finished_parent")
    binding = p.read_json(root / BASE / "material_binding/A.json")
    tasks = {row["task_id"]: row for row in parent["tasks"]}
    CACHE.mkdir(parents=True, exist_ok=True)
    sources = {path: p.sha(root / path) for path in source_paths}
    groups, points, updates, source_admissions = {}, [], {}, []
    numeric_rows = []
    for run in parent["runs"]:
        updates[run["key"]] = []
        for epoch in (0, 5):
            key = f"{run['key']}_epoch{epoch}"
            relative = f"{PARENT}/runs/{run['key']}/rounds/epoch{epoch}"
            directory = root / relative
            info, blocks, data = vectors(root, relative)
            groups_config = info["optimizer_snapshot"]["groups"]
            clip = info["optimizer_snapshot"]["clip"]
            reference, stable_diagnostics = numeric.pullback(
                data["G"],
                data["first_moment"],
                data["second_moment"],
                -data["gJ"],
                blocks,
                groups_config,
                clip,
            )
            cpu_original, cpu_diagnostics = numeric.pullback(
                data["G"],
                data["first_moment"],
                data["second_moment"],
                -data["gJ"],
                blocks,
                groups_config,
                clip,
                stable=False,
                dtype=torch.float32,
            )
            subtract64, _ = numeric.pullback(
                data["G"],
                data["first_moment"],
                data["second_moment"],
                -data["gJ"],
                blocks,
                groups_config,
                clip,
                stable=False,
            )
            reference_path = CACHE / "reference_vectors" / (key + ".safetensors")
            reference_path.parent.mkdir(parents=True, exist_ok=True)
            p.require(not reference_path.exists(), "proxy.no_reference_overwrite")
            save_file({"a_reference": reference}, str(reference_path))
            numeric_row = p.record(
                "proxy_saved_a_comparison",
                key=key,
                run=run,
                epoch=epoch,
                saved_CUDA_a_vs_stable_FP64=numeric.compare(data["a"], reference),
                old_CPU_FP32_vs_saved_CUDA=numeric.compare(cpu_original, data["a"]),
                subtractive_FP64_vs_stable_FP64=numeric.compare(subtract64, reference),
                stable=stable_diagnostics,
                CPU_original=cpu_diagnostics,
                actual_historical_gradient_max=float(data["G"].abs().max()),
                original_virtual_clip=info["virtual_step"]["clipping_active"],
                C_and_pi_influence_not_yet_evaluated=True,
            )
            p.write_once(out / "numeric" / (key + ".json"), numeric_row)
            numeric_rows.append(numeric_row)
            generated = p.read_json(directory / "feedback/generation_manifest.json")
            scoring = p.read_json(directory / "feedback/scoring_report.json")
            p.require(
                generated["complete"]
                and scoring["complete"]
                and scoring["denominator"] == 360
                and len(generated["trajectories"]) == 360,
                "proxy.original_complete360",
            )
            score_by_index = {row["index"]: row for row in scoring["scores"]}
            p.require(set(score_by_index) == set(range(360)), "proxy.no_missing_score")
            point = p.read_json(directory / "virtual_point/point.json")
            positive = []
            for item in generated["trajectories"]:
                job = item["job"]
                scored = score_by_index[job["index"]]
                p.require(
                    scored["task_id"] == job["task"]["task_id"]
                    and scored["repeat"] == job["repeat"]
                    and scored["Q"] in (0, 1),
                    "proxy.registered_task_repeat_score",
                )
                if not scored["Q"]:
                    continue
                raw = (root / item["path"]).read_bytes()
                p.require(
                    len(raw) == item["bytes"] and p.sha(raw) == item["sha256"],
                    "proxy.saved_positive_session_bytes",
                )
                session = json.loads(gzip.decompress(raw))
                p.require(
                    session["id"] == scored["session_id"], "proxy.saved_positive_session_identity"
                )
                turns = []
                for turn in session["turns"]:
                    receipt = turn["provider_receipt"]
                    p.require(receipt["point_id"] == point["id"], "proxy.saved_same_virtual_point")
                    turns.append(
                        dict(
                            prompt=receipt["prompt_input_ids"],
                            tokens=receipt["generated_token_ids"],
                            logps=receipt["sampled_token_logprobs"],
                        )
                    )
                content = dict(parameter_digest=point["parameter_digest"], turns=turns)
                content_id = p.sha(p.encode(content))
                cache_path = CACHE / "positive_inputs" / (content_id + ".json.gz")
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                packed = gzip.compress(p.encode(content), compresslevel=1, mtime=0)
                if not cache_path.exists():
                    with cache_path.open("xb") as stream:
                        stream.write(packed)
                positive.append(
                    dict(
                        index=job["index"],
                        task_id=scored["task_id"],
                        source_cluster=tasks[scored["task_id"]]["source_cluster"],
                        repeat=job["repeat"],
                        sampling_seed=job["seed"],
                        input_id=content_id,
                        path=str(cache_path),
                        bytes=len(packed),
                        sha256=p.sha(packed),
                        responses=len(turns),
                        tokens=sum(len(t["tokens"]) for t in turns),
                    )
                )
            p.require(len(positive) == scoring["qualified"], "proxy.all_existing_positive_terms")
            signature = dict(
                optimizer_snapshot=info["optimizer_snapshot"]["id"],
                G=info["G_digest"],
                gJ=p.read_json(directory / "gJ.json")["gJ_digest"],
                virtual_parameter_digest=point["parameter_digest"],
                material_binding_id=binding["id"],
                positive=[
                    {k: row[k] for k in ("index", "task_id", "repeat", "sampling_seed", "input_id")}
                    for row in positive
                ],
            )
            signature_id = p.sha(p.encode(signature))
            if signature_id not in groups:
                groups[signature_id] = dict(
                    key=key,
                    relative=relative,
                    epoch=epoch,
                    seed=run["seed"],
                    signature_id=signature_id,
                    aliases=[],
                    positive=positive,
                    point=point,
                    blocks=blocks,
                )
            entry = dict(
                key=key,
                run=run,
                epoch=epoch,
                relative=relative,
                reference_path=str(reference_path),
                numeric_report_id=numeric_row["id"],
                scoring_id=scoring["id"],
                gradient_id=info["id"],
                signature_id=signature_id,
                positive=len(positive),
                repeat_counts={
                    str(repeat): sum(row["repeat"] == repeat for row in positive)
                    for repeat in (1, 2)
                },
                concentration=concentration(positive),
            )
            groups[signature_id]["aliases"].append(entry)
            points.append(entry)
            updates[run["key"]].append(
                p.read_json(directory / "distribution_update.json")["pi_next"]
            )
            source_admissions.append(
                dict(
                    key=key,
                    optimizer_snapshot_id=info["optimizer_snapshot"]["id"],
                    source_score_id=scoring["id"],
                    positive_session_records_read=len(positive),
                    zero_sessions_read=0,
                )
            )
            print(
                json.dumps(
                    dict(
                        event="saved_numeric_point_complete",
                        key=key,
                        a_relative_L2=numeric_row["saved_CUDA_a_vs_stable_FP64"]["relative_L2"],
                        positives=len(positive),
                        at=p.now(),
                    )
                ),
                flush=True,
            )
    p.require(
        len(points) == 12 and sum(row["positive"] for row in points) == 652,
        "proxy.fixed_twelve_points_and_positive_cap",
    )
    plan = p.record(
        "anchored_proxy_audit_plan",
        audit_sha256=AUDIT_SHA,
        parent_plan_id=parent["id"],
        parent_matrix_id=completed["id"],
        sources=sources,
        code_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        points=points,
        jobs=list(groups.values()),
        source_admissions=source_admissions,
        cache_root=str(CACHE),
        extra_generation_calls=0,
        extra_financial_scores=0,
        max_extra_class_passes=12,
        max_extra_class_sequence_tokens=215307588,
        max_positive_replay_trajectories=652,
        max_replayed_sampled_tokens=166346,
        unique_class_passes_planned=len(groups),
        unique_positive_replays_planned=sum(len(job["positive"]) for job in groups.values()),
        maximum_workers=2,
        minimum_free_GPU_MiB=61440,
        minimum_host_available_bytes=512 * 2**30,
        numeric_limits=dict(relative_weighted_C_RMS=1e-3, weighted_pi_TV=1e-5),
        direction_repeat_denominator=180,
        leave_one_out_full_denominator=360,
        delayed_C_requires_all_numeric_points_admitted=True,
        at=p.now(),
    )
    p.write_once(out / "plan.json", plan)
    summary = p.record(
        "proxy_numeric_inventory",
        plan_id=plan["id"],
        scalar_control=numeric.cold_counterexample(),
        rounds=numeric_rows,
        method_exposure=exposure(binding, updates),
        points=12,
        unique_jobs=len(groups),
        positive_sessions_read=652,
        positive_replays_planned=plan["unique_positive_replays_planned"],
        extra_generation_calls=0,
        extra_financial_scores=0,
        C_and_pi_gate_pending=True,
    )
    p.write_once(out / "numeric_inventory.json", summary)
    print(
        json.dumps(
            dict(
                plan_id=plan["id"],
                unique_jobs=len(groups),
                planned_positive_replays=plan["unique_positive_replays_planned"],
                status="AWAITING_REGISTERED_G_PROJECTIONS",
            )
        ),
        flush=True,
    )
    return plan
