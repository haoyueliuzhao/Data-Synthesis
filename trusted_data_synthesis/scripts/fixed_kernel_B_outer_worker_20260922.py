"""Durable B step-200 population preparation and sealed-feedback replay.

The numerical kernels remain the frozen class-gradient, virtual AdamW,
segmented score-function replay and C-only dual-KL implementations. Durability
is placed around complete population passes and individual feedback responses.
"""

import gc
import importlib
from collections import Counter
from pathlib import Path

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_B_outer_worker_20260922.py"
PACKAGES, STATES, DENOMINATOR = 3529, 1645, 360


def _common():
    return importlib.import_module("fixed_kernel_B_common_20260922")


def _run(seed):
    p.require(type(seed) is int and seed in (11, 29, 47), "B_outer.registered_seed")
    return dict(key=f"B_delayed_c_{seed}", seed=seed, pool="B", condition="delayed_c")


def _reuse(path, kind, expected):
    if not path.exists():
        return None
    record = p.checked(p.read_json(path), kind)
    p.require(
        all(record.get(key) == value for key, value in expected.items()),
        "B_outer.reused_record_identity",
    )
    return record


def _prefix_binding(plan, report, saved, run):
    p.require(
        report["plan_id"] == plan["id"]
        and report["job_key"] == f"B_prefix_{run['seed']}"
        and report["complete"] is True
        and report["completed_updates"] == 200
        and report["snapshot_id"] == saved["snapshot"]["id"]
        and saved["completed_updates"] == saved["rng"]["schedule_cursor"] == 200,
        "B_outer.complete_original_prefix200",
    )
    return dict(
        plan_id=plan["id"],
        job_key=run["key"],
        prefix_checkpoint_sha256=report["checkpoint_sha256"],
        prefix_snapshot_id=saved["snapshot"]["id"],
    )


def _restore_rng(c, saved):
    c.s.restore_rng(saved["rng"])
    actual = c.s.capture_rng(200)
    p.require(
        torch.equal(actual["cpu"], saved["rng"]["cpu"])
        and len(actual["cuda"]) == len(saved["rng"]["cuda"])
        and all(
            torch.equal(left, right)
            for left, right in zip(actual["cuda"], saved["rng"]["cuda"], strict=True)
        ),
        "B_outer.restored_prefix_Torch_CPU_and_CUDA_RNG",
    )


def _population(c, root, directory, plan, lineage, model, names, bound, attempt):
    path = directory / "population.pt"
    binding = plan["materials"]["binding"]
    authority = dict(
        **lineage,
        material_binding_id=binding["id"],
        pi_sha256=p.sha(p.encode(binding["prior"])),
        optimizer_snapshot_id=bound.snapshot["id"],
    )
    if path.exists():
        saved = torch.load(path, map_location="cpu", weights_only=False)
        p.require(
            saved["kind"] == "B_full_population" and saved["binding"] == authority,
            "B_outer.population_same_prefix_and_materials",
        )
        population = c.old.classes.PopulationGradients(
            tuple(saved["keys"]),
            tuple(saved["names"]),
            tuple(saved["shapes"]),
            saved["matrix"],
            {name: value.to(names[name].device) for name, value in saved["G"].items()},
            saved["accounting"],
        )
        p.require(
            c.old.gate.tensor_digest(population.G) == saved["G_digest"],
            "B_outer.saved_full_G_digest",
        )
    else:
        reference = plan["materials"]["trajectory_cache"]
        cache_root = Path(root) / reference["cache_root"]
        manifest = p.read_json(cache_root / "manifest.json")
        p.require(manifest["id"] == reference["manifest_id"], "B_outer.original_B_cache_manifest")
        cache = c.old.trajectory_materials.load_pool(cache_root, manifest, "B")
        c.old.classes.admit(cache, binding)
        c.reserve("population", lineage["job_key"], attempt, 0)
        population = c.old.classes._compute(
            model,
            cache,
            binding["prior"],
            binding["mu"],
            event_sink=lambda event: (
                c.emit(dict(job_key=lineage["job_key"], **event))
                if event["completed_packages"] % 25 == 0
                else None
            ),
        )
        p.require(
            population.accounting["packages"] == PACKAGES
            and population.accounting["states"] == STATES,
            "B_outer.full_B3529_packages1645_states",
        )
        c.s.atomic_torch(
            path,
            dict(
                kind="B_full_population",
                binding=authority,
                keys=population.keys,
                names=population.names,
                shapes=population.shapes,
                matrix=population.matrix,
                G={name: value.detach().cpu() for name, value in population.G.items()},
                G_digest=c.old.gate.tensor_digest(population.G),
                accounting=population.accounting,
            ),
        )
    c.old.classes.validate_support(population.keys, binding["prior"], binding["mu"])
    p.require(
        population.accounting["packages"] == PACKAGES
        and population.accounting["states"] == STATES
        and len(population.keys) == STATES
        and tuple(names) == population.names
        and population.matrix.dtype == torch.float32
        and population.matrix.device.type == "cpu"
        and tuple(population.matrix.shape)
        == (STATES, sum(value.numel() for value in names.values()))
        and population.shapes == tuple(value.shape for value in names.values()),
        "B_outer.complete_saved_population_coordinates",
    )
    return population


def _prepare(c, root, run, attempt, required_MiB):
    directory = c.RAW / "outer" / run["key"]
    plan = c.read_protocol(root)
    existing = _reuse(
        directory / "prepare_report.json",
        "B_outer_prepared",
        dict(plan_id=plan["id"], job_key=run["key"], complete=True),
    )
    if existing is not None:
        return existing
    c.capacity_boundary("population", required_MiB=required_MiB)
    plan, prefix, saved, model, names, optimizer = c.restore_prefix_model(root, run["seed"])
    lineage = _prefix_binding(plan, prefix, saved, run)
    bound = c.old.adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
    p.require(
        bound.snapshot["id"] == lineage["prefix_snapshot_id"], "B_outer.exact_Adam200_binding"
    )
    try:
        population = _population(c, root, directory, plan, lineage, model, names, bound, attempt)
        virtual = c.old.adam.virtual_step(bound, population.G)
        full_G = p.record(
            "B_outer_actual_G",
            **lineage,
            accounting=population.accounting,
            optimizer_snapshot=bound.snapshot,
            virtual_step=virtual["diagnostics"],
            G_digest=c.old.gate.tensor_digest(population.G),
            pi=plan["materials"]["binding"]["prior"],
            real_completed_updates=200,
            first_distribution_update=True,
            population_path=str(directory / "population.pt"),
        )
        c.write(directory / "full_G.json", full_G)
        point = c.point_record(
            directory / "virtual_point",
            model,
            virtual["theta_bar"],
            plan,
            run,
            step=200,
            kind="delayed_single_virtual_step",
            origin=virtual["diagnostics"]["id"],
            source_manifest_id=plan["materials"]["source_manifest_id"],
        )
        c.old.adam._verify(bound)
        _restore_rng(c, saved)
        result = p.record(
            "B_outer_prepared",
            **lineage,
            complete=True,
            run=run,
            step=200,
            full_G_id=full_G["id"],
            point_id=point["id"],
            point=point,
            population_path=str(directory / "population.pt"),
            source_manifest_id=point["source_manifest_id"],
            real_model_and_Adam_unchanged=True,
            prefix_RNG_restored=True,
            feedback_generated=False,
            private_feedback_scored=False,
        )
        c.write(directory / "prepare_report.json", result)
        return result
    finally:
        c.old.adam._verify(bound)
        _restore_rng(c, saved)


def prepare(root, seed, attempt, required_MiB=32768):
    c, run = _common(), _run(seed)
    try:
        with c.locked(c.RAW / "outer" / run["key"] / "worker.lock", blocking=False):
            return _prepare(c, Path(root), run, attempt, required_MiB)
    finally:
        gc.collect()
        torch.cuda.empty_cache()


def feedback_inventory(c, plan, run, point):
    directory = c.RAW / "generation/feedback" / run["key"]
    generated = p.checked(
        p.read_json(directory / "generation_manifest.json"), "anchored_generation_manifest"
    )
    scored = p.checked(
        p.read_json(directory / "scoring_report.json"), "anchored_independent_scoring"
    )
    expected = c.old.feedback.registration(
        plan["dev_tasks"], pool="B", seed=run["seed"], round_index=1, stochastic=True
    )
    trajectories = generated["trajectories"]
    p.require(
        generated["complete"] is True
        and generated["stochastic"] is True
        and generated["point_id"] == scored["point_id"] == point["id"]
        and generated["source_manifest_id"]
        == scored["source_manifest_id"]
        == point["source_manifest_id"]
        and generated["tasks"] == plan["dev_tasks"]
        and len(trajectories) == DENOMINATOR
        and [item["job"] for item in trajectories] == expected
        and scored["complete"] is True
        and scored["denominator"] == DENOMINATOR
        and scored["generation_manifest_id"] == generated["id"]
        and len(scored["scores"]) == DENOMINATOR,
        "B_outer.complete_sealed_B360_feedback_only",
    )
    by_index = {row["index"]: row for row in scored["scores"]}
    p.require(set(by_index) == set(range(DENOMINATOR)), "B_outer.fixed360_score_indices")
    responses, positives = [], []
    for item in trajectories:
        index = item["job"]["index"]
        score, task = by_index[index], item["job"]["task"]
        p.checked(item, "anchored_generated_trajectory")
        p.require(
            item["point_id"] == point["id"]
            and item["private_assessment_performed"] is False
            and score["session_id"] == item["session_id"]
            and score["task_id"] == task["task_id"]
            and score["repeat"] == item["job"]["repeat"]
            and type(score["Q"]) is int
            and score["Q"] in (0, 1),
            "B_outer.saved_binary_reward_and_task_binding",
        )
        if score["Q"] == 0:
            continue
        positives.append(
            dict(
                index=index,
                task_id=task["task_id"],
                source_cluster=task["source_cluster"],
                repeat=score["repeat"],
            )
        )
        session = c.old.feedback.read_session(c.RAW, item)
        # The independent scorer already checked all receipts, including zero-Q sessions.
        for offset, turn in enumerate(session["turns"]):
            receipt = turn["provider_receipt"]
            responses.append(
                dict(
                    trajectory=index,
                    turn=offset,
                    response_index=turn["response_index"],
                    receipt_id=receipt["id"],
                    tokens=len(receipt["generated_token_ids"]),
                    last_in_trajectory=offset == len(session["turns"]) - 1,
                )
            )
    p.require(scored["qualified"] == len(positives), "B_outer.fixed_qualified_count")
    inventory = p.record(
        "B_feedback_response_inventory",
        plan_id=plan["id"],
        job_key=run["key"],
        point_id=point["id"],
        generation_manifest_id=generated["id"],
        scoring_report_id=scored["id"],
        denominator=DENOMINATOR,
        responses=responses,
        required_responses=len(responses),
        positives=positives,
        zero_reward_trajectories=DENOMINATOR - len(positives),
    )
    return generated, scored, inventory


def recover_accumulator(c, directory, authority, theta):
    paths = {int(path.stem): path for path in directory.glob("*.pt") if path.stem.isdigit()}
    cursor = max(paths, default=0)
    p.require(
        set(paths) == set(range(1, cursor + 1)) and cursor <= authority["required_responses"],
        "B_outer.contiguous_response_checkpoints",
    )
    if cursor == 0:
        return 0, {name: torch.zeros_like(value) for name, value in theta.items()}, Counter()
    saved = torch.load(paths[cursor], map_location="cpu", weights_only=False)
    p.require(
        saved["kind"] == "B_feedback_response_accumulator"
        and saved["authority"] == authority
        and saved["cursor"] == cursor
        and saved["accounting"]["responses_replayed"] == cursor
        and set(saved["sum_cpu"]) == set(theta)
        and c.old.gate.tensor_digest(saved["sum_cpu"]) == saved["sum_digest"],
        "B_outer.same_sealed_response_accumulator",
    )
    p.require(
        all(
            value.dtype == torch.float32
            and value.shape == theta[name].shape
            and bool(torch.isfinite(value).all())
            for name, value in saved["sum_cpu"].items()
        ),
        "B_outer.FP32_complete_accumulator_coordinates",
    )
    return (
        cursor,
        {name: value.to(theta[name].device) for name, value in saved["sum_cpu"].items()},
        Counter(saved["accounting"]),
    )


def replay_responses(
    c, directory, authority, theta, responses, attempt, response_gradient, required_MiB
):
    """Each atomic sum includes its cursor; a crash never loses committed progress."""
    cursor, total, accounting = recover_accumulator(c, directory, authority, theta)
    p.require(
        len(responses) == authority["required_responses"], "B_outer.registered_response_inventory"
    )
    c.set_replay_required(authority["job_key"], len(responses))
    for offset in range(cursor, len(responses)):
        response = responses[offset]
        c.capacity_boundary("feedback", required_MiB=required_MiB)
        c.reserve("feedback_response", authority["job_key"], attempt, offset)
        gradient, used = response_gradient(response)
        p.require(
            set(gradient) == set(total)
            and all(
                value.dtype == torch.float32
                and value.device == total[name].device
                and value.shape == total[name].shape
                and bool(torch.isfinite(value).all())
                for name, value in gradient.items()
            ),
            "B_outer.finite_original_FP32_response_gradient",
        )
        for name in total:
            total[name].add_(gradient[name], alpha=1 / DENOMINATOR)
        accounting["responses_replayed"] += 1
        accounting["sampled_tokens_with_parameter_derivative"] += response["tokens"]
        accounting["cached_forward_target_positions"] += used["cached_forward_target_positions"]
        accounting["positive_reward_trajectories"] += int(response["last_in_trajectory"])
        checkpoint = dict(
            kind="B_feedback_response_accumulator",
            authority=authority,
            cursor=offset + 1,
            accounting=dict(accounting),
            sum_cpu={name: value.detach().cpu().clone() for name, value in total.items()},
            sum_digest=c.old.gate.tensor_digest(total),
            last_response=response,
        )
        c.s.atomic_torch(directory / f"{offset + 1:04d}.pt", checkpoint)
        c.emit(
            dict(
                event="B_feedback_response_committed",
                job_key=authority["job_key"],
                completed_responses=offset + 1,
                required_responses=len(responses),
            )
        )
        del gradient, checkpoint
    p.require(
        all(bool(torch.isfinite(value).all()) for value in total.values()),
        "B_outer.finite_complete_gJ",
    )
    return total, accounting


def concentration(positives):
    tasks = Counter(row["task_id"] for row in positives)
    clusters = Counter(row["source_cluster"] for row in positives)
    count = len(positives)
    return dict(
        positive_trajectories=count,
        positive_unique_tasks=len(tasks),
        positive_unique_CIKs=len(clusters),
        positive_counts_by_task=dict(tasks),
        positive_counts_by_CIK=dict(clusters),
        largest_task_share=max(tasks.values(), default=0) / count if count else None,
        largest_CIK_share=max(clusters.values(), default=0) / count if count else None,
        new_point_cross_repeat_reliability="NOT_MEASURED",
        extra_gradient_or_feedback_calls=0,
        concentration_is_not_cross_repeat_gradient_reliability=True,
    )


def _replay(c, root, run, attempt, required_MiB):
    directory = c.RAW / "outer" / run["key"]
    plan = c.read_protocol(root)
    existing = _reuse(
        directory / "report.json",
        "B_completed_outer",
        dict(plan_id=plan["id"], job_key=run["key"], complete=True, numeric_guard_passed=True),
    )
    if existing is not None:
        return existing
    prepared = p.checked(p.read_json(directory / "prepare_report.json"), "B_outer_prepared")
    c.capacity_boundary("feedback", required_MiB=required_MiB)
    plan, prefix, saved, model, names, optimizer = c.restore_prefix_model(root, run["seed"])
    lineage = _prefix_binding(plan, prefix, saved, run)
    p.require(
        all(prepared[key] == value for key, value in lineage.items()), "B_outer.replay_same_prefix"
    )
    bound = c.old.adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
    p.require(bound.snapshot["id"] == lineage["prefix_snapshot_id"], "B_outer.replay_exact_Adam200")
    try:
        p.require(
            (directory / "population.pt").exists(), "B_outer.replay_requires_saved_population"
        )
        population = _population(c, root, directory, plan, lineage, model, names, bound, attempt)
        full_G = p.checked(p.read_json(directory / "full_G.json"), "B_outer_actual_G")
        p.require(
            full_G["id"] == prepared["full_G_id"]
            and full_G["G_digest"] == c.old.gate.tensor_digest(population.G)
            and full_G["optimizer_snapshot"] == bound.snapshot,
            "B_outer.replay_saved_G_and_real_optimizer",
        )
        virtual = c.old.adam.virtual_step(bound, population.G)
        theta = virtual["theta_bar"]
        point = p.checked(
            p.read_json(directory / "virtual_point/point.json"), "anchored_model_parameter_point"
        )
        p.require(
            point == prepared["point"]
            and point["id"] == prepared["point_id"]
            and point["parameter_digest"] == c.old.gate.tensor_digest(theta)
            and point["origin_id"] == virtual["diagnostics"]["id"],
            "B_outer.exact_saved_virtual_point",
        )
        p.require(
            all(
                value.device.type == "cuda" and value.dtype == torch.float32
                for value in theta.values()
            ),
            "B_outer.actual_GPU_FP32_proxy_coordinates",
        )
        generated, scored, inventory = feedback_inventory(c, plan, run, point)
        c.write(directory / "response_inventory.json", inventory)
        authority = dict(
            **lineage,
            point_id=point["id"],
            full_G_id=full_G["id"],
            inventory_id=inventory["id"],
            required_responses=inventory["required_responses"],
        )
        current = {"trajectory": None, "session": None}

        def response_gradient(response):
            index = response["trajectory"]
            if current["trajectory"] != index:
                current.update(
                    trajectory=index,
                    session=c.old.feedback.read_session(c.RAW, generated["trajectories"][index]),
                )
            turn = current["session"]["turns"][response["turn"]]
            receipt = turn["provider_receipt"]
            p.require(
                receipt["id"] == response["receipt_id"]
                and turn["response_index"] == response["response_index"],
                "B_outer.exact_saved_response_order",
            )
            with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                _, gradient, used = c.old.feedback.segmented.segmented_logp(
                    model,
                    theta,
                    receipt["prompt_input_ids"],
                    receipt["generated_token_ids"],
                    expected=receipt["sampled_token_logprobs"],
                    block_size=8,
                )
            return gradient, used

        gJ, accounting = replay_responses(
            c,
            directory / "replay",
            authority,
            theta,
            inventory["responses"],
            attempt,
            response_gradient,
            required_MiB,
        )
        accounting["zero_reward_gradient_terms_skipped"] = inventory["zero_reward_trajectories"]
        feedback_report = p.record(
            "anchored_full_trajectory_feedback_gradient",
            point_id=point["id"],
            scoring_report_id=scored["id"],
            denominator=DENOMINATOR,
            accounting=dict(accounting),
            gJ_digest=c.old.gate.tensor_digest(gJ),
            all_sampled_error_and_EOS_tokens_of_positive_trajectories_included=True,
            zero_reward_authentic_receipts_validated=True,
            zero_reward_GPU_replay_not_claimed=True,
            length_normalization=False,
            coefficient="1/360",
            accumulator_dtype="GPU FP32",
            required_responses=inventory["required_responses"],
            new_point_cross_repeat_reliability="NOT_MEASURED",
        )
        binding, pi = plan["materials"]["binding"], plan["materials"]["binding"]["prior"]
        pullback = c.old.adam.pullback(
            bound, population.G, {name: -value for name, value in gJ.items()}
        )
        contributions = population.centered(pi, binding["mu"], pullback["a"])
        rewards = [row["Q"] for row in sorted(scored["scores"], key=lambda row: row["index"])]
        updated = c.old.distribution.update_distribution(
            pi,
            binding["prior"],
            contributions["C"],
            binding["mu"],
            rewards,
            control_tasks=binding["control_tasks"],
            condition="c_only_anchored",
            registered_complete=True,
        )
        temperatures = c.old.distribution.anchored.contribution_temperatures(
            contributions["C"],
            pi,
            binding["mu"],
            control_tasks=binding["control_tasks"],
        )
        guard = c.d.new_point_numeric_guard(
            population,
            bound,
            gJ,
            pullback["a"],
            contributions["C"],
            updated,
            pi,
            binding,
            scored["qualified"],
            plan["numeric_limits"],
        )
        for name, value in (
            ("gJ", feedback_report),
            ("pullback", pullback["diagnostics"]),
            ("C", contributions),
            ("distribution_update", updated),
            ("numeric_guard", guard),
        ):
            c.write(directory / (name + ".json"), value)
        scale = p.record(
            "B_raw_Contribution_scale",
            C_id=contributions["id"],
            R=temperatures["global_weighted_RMS"],
            T_C=temperatures["T_C"],
            temperature=temperatures,
            raw_C_not_rescaled=True,
        )
        c.write(directory / "C_scale.json", scale)
        if not (directory / "final_vectors.pt").exists():
            c.s.atomic_torch(
                directory / "final_vectors.pt",
                dict(
                    binding=authority,
                    G={name: value.detach().cpu() for name, value in population.G.items()},
                    gJ={name: value.detach().cpu() for name, value in gJ.items()},
                    a={name: value.detach().cpu() for name, value in pullback["a"].items()},
                ),
            )
        p.require(guard["passed"], "B_outer.numeric_guard_STOP_without_formula_change")
        c.old.adam._verify(bound)
        _restore_rng(c, saved)
        result = p.record(
            "B_completed_outer",
            **lineage,
            run=run,
            complete=True,
            step=200,
            numeric_guard_passed=True,
            numeric_guard_id=guard["id"],
            distribution_update_id=updated["id"],
            feedback_report_id=feedback_report["id"],
            C_id=contributions["id"],
            C_scale_id=scale["id"],
            full_G_id=full_G["id"],
            feedback_sessions=DENOMINATOR,
            denominator=DENOMINATOR,
            qualified=scored["qualified"],
            generate_calls=sum(item["actual_generate_calls"] for item in generated["trajectories"]),
            required_replay_responses=inventory["required_responses"],
            update_status=updated["status"],
            positive_feedback_concentration=concentration(inventory["positives"]),
            prefix_RNG_restored=True,
            real_model_and_Adam_unchanged=True,
            no_direct_policy_gradient_student_step=True,
            novelty_term_used=False,
        )
        c.write(directory / "report.json", result)
        return result
    finally:
        c.old.adam._verify(bound)
        _restore_rng(c, saved)


def replay(root, seed, attempt, required_MiB=51200):
    c, run = _common(), _run(seed)
    try:
        with c.locked(c.RAW / "outer" / run["key"] / "worker.lock", blocking=False):
            return _replay(c, Path(root), run, attempt, required_MiB)
    finally:
        gc.collect()
        torch.cuda.empty_cache()
