"""One bounded replay of sealed B feedback; saved-point diagnostic, never a gate.

The real feedback sum and pullback use the original GPU FP32 kernels. CPU
linear projections reuse the *original* frozen Adam derivative coefficients;
they do not substitute a stabilized or otherwise revised Adam expression.
Every response commits both the original GPU FP32 1/360 accumulator and its
trajectory's unscaled CPU FP64 sum of the original FP32 response gradients,
making the last response checkpoint a trajectory vector.
"""

# ruff: noqa: E501 -- explicit evidence bindings and fixed-denominator definitions
import gc
import importlib
from collections import Counter
from pathlib import Path

import fixed_kernel_B_outer_worker_20260922 as outer
import fixed_kernel_proxy_direction_20260919 as direction
import numpy as np
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_B_direction_reliability_20260926.py"
DENOMINATOR, HALF_DENOMINATOR = 360, 180
LIMIT_C_RMS, LIMIT_PI_TV = 1e-5, 1e-5


def _common():
    return importlib.import_module("fixed_kernel_direction_calibration_common_20260926")


def _digest(c, values):
    return c.b.old.gate.tensor_digest(values)


def _valid_vector(values, theta, dtype=torch.float32):
    return set(values) == set(theta) and all(
        value.dtype == dtype
        and value.shape == theta[name].shape
        and bool(torch.isfinite(value).all())
        for name, value in values.items()
    )


def recover(c, directory, authority, theta, responses):
    paths = {int(path.stem): path for path in directory.glob("*.pt") if path.stem.isdigit()}
    cursor = max(paths, default=0)
    p.require(
        set(paths) == set(range(1, cursor + 1)) and cursor <= len(responses),
        "reliability.contiguous_response_cursor",
    )
    if not cursor:
        return (
            0,
            {name: torch.zeros_like(value) for name, value in theta.items()},
            {
                name: torch.zeros_like(value, device="cpu", dtype=torch.float64)
                for name, value in theta.items()
            },
            None,
            Counter(),
        )
    saved = torch.load(paths[cursor], map_location="cpu", weights_only=False)
    p.require(
        saved["kind"] == "B_direction_response_accumulator"
        and saved["authority"] == authority
        and saved["cursor"] == cursor
        and saved["last_response"] == responses[cursor - 1]
        and saved["trajectory"] == responses[cursor - 1]["trajectory"]
        and saved["accounting"]["responses_replayed"] == cursor,
        "reliability.saved_cursor_and_original_response_binding",
    )
    for key, dtype in (("sum_cpu", torch.float32), ("trajectory_cpu", torch.float64)):
        p.require(
            _valid_vector(saved[key], theta, dtype)
            and _digest(c, saved[key]) == saved[key + "_digest"],
            "reliability.saved_finite_original_FP32_total_and_CPU_FP64_trajectory",
        )
    total = {name: value.to(theta[name].device) for name, value in saved["sum_cpu"].items()}
    return cursor, total, saved["trajectory_cpu"], saved["trajectory"], Counter(saved["accounting"])


def replay_responses(
    c, directory, authority, theta, responses, attempt, response_gradient, required_MiB
):
    """The original ordered sum and trajectory vector commit in one atomic file."""
    p.require(
        len(responses) == authority["required_responses"], "reliability.fixed_response_inventory"
    )
    cursor, total, trajectory, current, accounting = recover(
        c, directory, authority, theta, responses
    )
    for offset in range(cursor, len(responses)):
        response = responses[offset]
        c.capacity_boundary("feedback", required_MiB=required_MiB)
        c.reserve("reliability_response", authority["job_key"], attempt, offset)
        gradient, used = response_gradient(response)
        p.require(
            _valid_vector(gradient, theta)
            and all(value.device == total[name].device for name, value in gradient.items()),
            "reliability.original_finite_GPU_FP32_response_gradient",
        )
        if current != response["trajectory"]:
            p.require(
                offset == 0 or responses[offset - 1]["last_in_trajectory"],
                "reliability.contiguous_original_trajectory_responses",
            )
            trajectory = {
                name: torch.zeros_like(value, device="cpu", dtype=torch.float64)
                for name, value in theta.items()
            }
            current = response["trajectory"]
        for name in total:
            total[name].add_(gradient[name], alpha=1 / DENOMINATOR)
            trajectory[name].add_(gradient[name].detach().cpu().double())
        accounting["responses_replayed"] += 1
        accounting["sampled_tokens_with_parameter_derivative"] += response["tokens"]
        accounting["cached_forward_target_positions"] += used["cached_forward_target_positions"]
        accounting["positive_reward_trajectories"] += int(response["last_in_trajectory"])
        checkpoint = dict(
            kind="B_direction_response_accumulator",
            authority=authority,
            cursor=offset + 1,
            trajectory=current,
            last_response=response,
            accounting=dict(accounting),
            sum_cpu={name: value.detach().cpu().clone() for name, value in total.items()},
            trajectory_cpu={
                name: value.detach().cpu().clone() for name, value in trajectory.items()
            },
            sum_cpu_digest=_digest(c, total),
            trajectory_cpu_digest=_digest(c, trajectory),
        )
        c.s.atomic_torch(directory / f"{offset + 1:04d}.pt", checkpoint)
        if hasattr(c, "emit"):
            c.emit(
                dict(
                    event="B_direction_response_committed",
                    job_key=authority["job_key"],
                    completed_responses=offset + 1,
                    required_responses=len(responses),
                )
            )
        del gradient, checkpoint
    return total, accounting


def original_linear_coefficients(adam, bound, G, names):
    """Read the registered implementation's derivative, not a new numeric kernel."""
    _, _, diagonal, norm, coefficient, active, _ = adam._evaluate(bound, G)

    def flatten(values):
        return torch.cat([values[name].detach().cpu().reshape(-1).double() for name in names])

    return dict(
        diagonal=flatten(diagonal),
        G=flatten(G),
        norm=float(norm),
        coefficient=float(coefficient),
        active=active,
        epsilon=bound.clip_epsilon,
    )


def load_original_population(c, path, parent, lineage, bound, names):
    """Read-only loader with deliberately no population-computation fallback."""
    binding = parent["materials"]["binding"]
    expected = dict(
        **lineage,
        material_binding_id=binding["id"],
        pi_sha256=p.sha(p.encode(binding["prior"])),
        optimizer_snapshot_id=bound.snapshot["id"],
    )
    saved = torch.load(path, map_location="cpu", weights_only=False)
    p.require(
        saved["kind"] == "B_full_population" and saved["binding"] == expected,
        "reliability.same_saved_B_population_at_prefix200",
    )
    population = c.b.old.classes.PopulationGradients(
        tuple(saved["keys"]),
        tuple(saved["names"]),
        tuple(saved["shapes"]),
        saved["matrix"],
        {name: value.to(names[name].device) for name, value in saved["G"].items()},
        saved["accounting"],
    )
    p.require(
        _digest(c, population.G) == saved["G_digest"]
        and population.accounting["packages"] == 3529
        and population.accounting["states"] == len(population.keys) == 1645
        and tuple(names) == population.names
        and population.shapes == tuple(value.shape for value in names.values())
        and population.matrix.dtype == torch.float32
        and population.matrix.device.type == "cpu"
        and tuple(population.matrix.shape)
        == (1645, sum(value.numel() for value in names.values())),
        "reliability.saved_B_population_complete_coordinates",
    )
    c.b.old.classes.validate_support(population.keys, binding["prior"], binding["mu"])
    return population


def cpu_linear_pullback(coefficients, covectors):
    """FP64 application of saved original FP32 coefficients; linkage is gated."""
    vector = covectors.detach().cpu().double()
    one = vector.ndim == 1
    if one:
        vector = vector[:, None]
    p.require(
        vector.ndim == 2 and vector.shape[0] == coefficients["G"].numel(),
        "reliability.linear_coordinates",
    )
    scaled = coefficients["diagonal"][:, None] * vector
    if coefficients["active"] and coefficients["norm"] != 0:
        radial = coefficients["G"] @ scaled
        radial /= coefficients["norm"] * (coefficients["norm"] + coefficients["epsilon"])
        scaled -= coefficients["G"][:, None] * radial[None, :]
    answer = coefficients["coefficient"] * scaled
    p.require(bool(torch.isfinite(answer).all()), "reliability.finite_CPU_linear_projection")
    return answer[:, 0] if one else answer


def _project_trajectories(
    c, directory, authority, responses, positives, population, coefficients, geometry
):
    ends = {
        row["trajectory"]: offset + 1
        for offset, row in enumerate(responses)
        if row["last_in_trajectory"]
    }
    p.require(
        set(ends) == {row["index"] for row in positives},
        "reliability.every_positive_has_one_saved_trajectory_vector",
    )
    projected = np.empty((len(population.keys), len(positives)), dtype=np.float64)
    for start in range(0, len(positives), 8):
        vectors = []
        for item in positives[start : start + 8]:
            saved = torch.load(
                directory / f"{ends[item['index']]:04d}.pt", map_location="cpu", weights_only=False
            )
            p.require(
                saved["authority"] == authority
                and saved["cursor"] == ends[item["index"]]
                and saved["trajectory"] == item["index"]
                and saved["last_response"]["last_in_trajectory"]
                and _digest(c, saved["trajectory_cpu"]) == saved["trajectory_cpu_digest"],
                "reliability.sealed_trajectory_vector",
            )
            vectors.append(
                torch.cat(
                    [
                        saved["trajectory_cpu"][name].reshape(-1).double()
                        for name in population.names
                    ]
                )
            )
        covectors = cpu_linear_pullback(coefficients, -torch.stack(vectors, dim=1))
        projected[:, start : start + len(vectors)] = direction.project(
            population.matrix, covectors, population.keys, geometry
        )
    return projected


def project_trajectories(*args, **kwargs):
    threads = torch.get_num_threads()
    try:
        torch.set_num_threads(16)
        return _project_trajectories(*args, **kwargs)
    finally:
        torch.set_num_threads(threads)


def equivalence(geometry, candidate, reference_C, reference_pi, positives):
    comparison = geometry.compare_C(candidate, geometry.flatten(reference_C))
    proposal, _ = geometry.propose(candidate, "c_only_anchored", positives)
    tv = geometry.TV(proposal, geometry.flatten(reference_pi))
    return dict(
        passed=comparison["relative_weighted_RMS"] <= LIMIT_C_RMS and tv <= LIMIT_PI_TV,
        C_comparison=comparison,
        pi_weighted_TV=tv,
        limits=dict(relative_weighted_C_RMS=LIMIT_C_RMS, weighted_pi_TV=LIMIT_PI_TV),
    )


def gradient_equivalence(candidate, reference):
    p.require(set(candidate) == set(reference), "reliability.saved_gJ_complete_coordinates")
    difference_squared, reference_squared, maximum = 0.0, 0.0, 0.0
    passed, exact = True, True
    for name, value in candidate.items():
        value = value.detach().cpu()
        expected = reference[name]
        p.require(
            value.dtype == expected.dtype == torch.float32
            and value.shape == expected.shape
            and bool(torch.isfinite(value).all())
            and bool(torch.isfinite(expected).all()),
            "reliability.saved_gJ_shape_dtype_finite",
        )
        passed = passed and torch.allclose(value, expected, rtol=1e-5, atol=1e-6)
        exact = exact and torch.equal(value, expected)
        delta = value.double() - expected.double()
        difference_squared += float(delta.square().sum())
        reference_squared += float(expected.double().square().sum())
        maximum = max(maximum, float(delta.abs().max()))
    return dict(
        passed=bool(passed),
        bitwise_equal=bool(exact),
        maximum_absolute_error=maximum,
        relative_L2=difference_squared**0.5 / max(reference_squared**0.5, 1e-30),
        L2_error=difference_squared**0.5,
        reference_L2=reference_squared**0.5,
        per_tensor_allclose_rtol=1e-5,
        per_tensor_allclose_atol=1e-6,
        nullspace_not_ignored_by_C_projection=True,
    )


def _norm(geometry, vector):
    mask = geometry.noncontrol
    weights = geometry.weights[mask] / geometry.weights[mask].sum()
    normalized = vector[mask] / geometry.mass[mask]
    return float(np.sqrt(np.sum(weights * normalized * normalized)))


def mechanism_analysis(projected, positives, tasks, geometry):
    """Task/CIK deletion is diagnostic and retains both fixed denominators."""
    full = projected.sum(axis=1) / DENOMINATOR
    baseline = geometry.flatten(geometry.pi)
    full_pi, full_status = geometry.propose(full, "c_only_anchored", len(positives))
    halves, proposals, half_rows = {}, {}, {}
    for repeat in (1, 2):
        selected = [i for i, row in enumerate(positives) if row["repeat"] == repeat]
        halves[repeat] = projected[:, selected].sum(axis=1) / HALF_DENOMINATOR
        proposals[repeat], status = geometry.propose(
            halves[repeat], "c_only_anchored", len(selected)
        )
        half_rows[str(repeat)] = dict(
            positive=len(selected),
            denominator=HALF_DENOMINATOR,
            status=status,
            self_score=float(halves[repeat] @ (proposals[repeat] - baseline)),
            weighted_pi_TV=geometry.TV(proposals[repeat], baseline),
        )
    both = all(half_rows[str(repeat)]["positive"] > 0 for repeat in (1, 2))
    cross = dict(
        S_1_to_2=float(halves[2] @ (proposals[1] - baseline)) if both else None,
        S_2_to_1=float(halves[1] @ (proposals[2] - baseline)) if both else None,
        interpretable=both,
        no_zero_half_regrouping=True,
    )
    summary, vectors = {}, {}
    for field in ("task_id", "source_cluster"):
        identifiers = sorted({row[field] for row in tasks})
        contributions, rows = [], []
        for identifier in identifiers:
            indices = [i for i, row in enumerate(positives) if row[field] == identifier]
            contribution = projected[:, indices].sum(axis=1) / DENOMINATOR
            contributions.append(contribution)
            reduced = full - contribution
            reduced_pi, status = geometry.propose(
                reduced, "c_only_anchored", len(positives) - len(indices)
            )
            compare = geometry.compare_C(reduced, full)
            reduced_halves, reduced_proposals, remaining = {}, {}, {}
            for repeat in (1, 2):
                removed = [i for i in indices if positives[i]["repeat"] == repeat]
                reduced_halves[repeat] = (
                    halves[repeat] - projected[:, removed].sum(axis=1) / HALF_DENOMINATOR
                )
                remaining[repeat] = half_rows[str(repeat)]["positive"] - len(removed)
                reduced_proposals[repeat], _ = geometry.propose(
                    reduced_halves[repeat], "c_only_anchored", remaining[repeat]
                )
            valid = all(remaining.values())
            rows.append(
                dict(
                    identifier=identifier,
                    positive_trajectories=len(indices),
                    fixed_full_denominator=DENOMINATOR,
                    fixed_half_denominator=HALF_DENOMINATOR,
                    vector_weighted_RMS=_norm(geometry, contribution),
                    signed_alignment_with_full_direction=float(contribution @ (full_pi - baseline)),
                    removed_status=status,
                    removed_C_weighted_cosine=compare["weighted_cosine"],
                    removed_C_relative_weighted_RMS_change=compare["relative_weighted_RMS"],
                    removed_pi_weighted_TV_change=geometry.TV(reduced_pi, full_pi),
                    removed_S_1_to_2=float(reduced_halves[2] @ (reduced_proposals[1] - baseline))
                    if valid
                    else None,
                    removed_S_2_to_1=float(reduced_halves[1] @ (reduced_proposals[2] - baseline))
                    if valid
                    else None,
                    removed_cross_interpretable=bool(valid),
                )
            )
        total_norms = sum(row["vector_weighted_RMS"] for row in rows)
        for row in rows:
            row["share_of_sum_group_vector_norms"] = (
                row["vector_weighted_RMS"] / total_norms if total_norms else None
            )
        summary[field] = rows
        vectors[field] = dict(
            identifiers=identifiers, C=torch.from_numpy(np.stack(contributions, axis=1))
        )
    return dict(
        fixed_total_denominator=DENOMINATOR,
        fixed_repeat_denominator=HALF_DENOMINATOR,
        halves=half_rows,
        cross=cross,
        half_C_comparison=geometry.compare_C(halves[1], halves[2]),
        full_status=full_status,
        full_self_score=float(full @ (full_pi - baseline)),
        full_weighted_pi_TV=geometry.TV(full_pi, baseline),
        grouped_influence_and_deletion=summary,
        grouping_population="original feedback tasks and source CIKs; C coordinates remain the complete B training-state support",
        group_vector_norms_are_nonadditive_due_to_cancellation=True,
        self_score_is_not_reliability=True,
        not_independent_task_generalization=True,
        no_seed_or_task_selection_authorized=True,
        not_a_stage2_selection_gate=True,
    ), dict(
        full_C=torch.from_numpy(full),
        repeat1_C=torch.from_numpy(halves[1]),
        repeat2_C=torch.from_numpy(halves[2]),
        groups=vectors,
    )


def _run(c, root, seed, attempt, required_MiB):
    p.require(type(seed) is int and seed in (11, 29, 47), "reliability.all_three_fixed_B_seeds")
    plan, old = c.read_protocol(root), c.b.old
    key = f"B_direction_reliability_{seed}"
    directory = c.RAW / "reliability" / key
    existing = directory / "report.json"
    if existing.exists():
        report = p.checked(p.read_json(existing), "B_direction_reliability_report")
        p.require(
            report["plan_id"] == plan["id"]
            and report["seed"] == seed
            and report["complete"] is True,
            "reliability.reuse_bound_complete_report",
        )
        return report
    parent = c.b.read_protocol(root)
    p.require(
        plan["parent_B_protocol_id"] == parent["id"], "reliability.registered_original_B_protocol"
    )
    old_run = outer._run(seed)
    original = c.b.RAW / "outer" / old_run["key"]
    admitted = plan["reliability_inputs"][str(seed)]
    p.require(
        admitted["job_key"] == key
        and admitted["original_job_key"] == old_run["key"]
        and Path(admitted["original_stage_directory"]).resolve() == original.resolve(),
        "reliability.exact_registered_input_directory",
    )
    for name in admitted["files"]:
        c.require_input(plan, seed, name)
    p.require(
        Path(admitted["files"]["population"]["path"]).resolve()
        == (original / "population.pt").resolve(),
        "reliability.registered_population_path",
    )
    p.require(
        (original / "population.pt").exists(), "reliability.saved_population_required_NO_recompute"
    )
    completed = p.checked(p.read_json(original / "report.json"), "B_completed_outer")
    prepared = p.checked(p.read_json(original / "prepare_report.json"), "B_outer_prepared")
    c.capacity_boundary("feedback", required_MiB=required_MiB)
    parent, prefix, saved, model, names, optimizer = c.b.restore_prefix_model(root, seed)
    lineage = outer._prefix_binding(parent, prefix, saved, old_run)
    bound = old.adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
    p.require(
        bound.snapshot["id"] == lineage["prefix_snapshot_id"]
        and all(prepared[name] == value for name, value in lineage.items()),
        "reliability.exact_original_step200",
    )
    try:
        population = load_original_population(
            c, original / "population.pt", parent, lineage, bound, names
        )
        full_G = p.checked(p.read_json(original / "full_G.json"), "B_outer_actual_G")
        p.require(
            full_G["id"] == completed["full_G_id"] == prepared["full_G_id"]
            and full_G["optimizer_snapshot"] == bound.snapshot,
            "reliability.saved_G_and_Adam_linkage",
        )
        virtual = old.adam.virtual_step(bound, population.G)
        theta, point = virtual["theta_bar"], prepared["point"]
        p.require(
            point["parameter_digest"] == old.gate.tensor_digest(theta)
            and point["origin_id"] == virtual["diagnostics"]["id"],
            "reliability.original_virtual_point",
        )
        generated, scored, inventory = outer.feedback_inventory(c.b, parent, old_run, point)
        p.require(
            inventory == p.read_json(original / "response_inventory.json")
            and inventory["required_responses"] == completed["required_replay_responses"]
            and inventory["required_responses"] == admitted["required_responses"]
            and len(inventory["positives"])
            == completed["qualified"]
            == admitted["positive_trajectories"],
            "reliability.original_sealed_inventory_no_new_scores",
        )
        authority = dict(
            plan_id=plan["id"],
            parent_B_protocol_id=parent["id"],
            job_key=key,
            seed=seed,
            original_outer_report_id=completed["id"],
            prefix_snapshot_id=bound.snapshot["id"],
            inventory_id=inventory["id"],
            full_G_id=full_G["id"],
            required_responses=inventory["required_responses"],
        )
        c.write(
            directory / "input_binding.json",
            p.record(
                "B_direction_reliability_inputs",
                **authority,
                new_G_passes=0,
                new_generation_calls=0,
                new_financial_assessments=0,
            ),
        )
        current = {"trajectory": None, "session": None}

        def response_gradient(response):
            index = response["trajectory"]
            if current["trajectory"] != index:
                current.update(
                    trajectory=index,
                    session=old.feedback.read_session(c.b.RAW, generated["trajectories"][index]),
                )
            turn = current["session"]["turns"][response["turn"]]
            receipt = turn["provider_receipt"]
            p.require(
                receipt["id"] == response["receipt_id"]
                and turn["response_index"] == response["response_index"],
                "reliability.exact_original_response",
            )
            with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                _, gradient, used = old.feedback.segmented.segmented_logp(
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
            directory / "responses",
            authority,
            theta,
            inventory["responses"],
            attempt,
            response_gradient,
            required_MiB,
        )
        p.require(
            accounting["responses_replayed"] == admitted["required_responses"]
            and accounting["positive_reward_trajectories"] == admitted["positive_trajectories"]
            and accounting["sampled_tokens_with_parameter_derivative"]
            == admitted["expected_output_tokens"],
            "reliability.exact_registered_response_trajectory_and_output_token_totals",
        )
        saved_vectors = torch.load(
            c.require_input(plan, seed, "final_vectors"), map_location="cpu", weights_only=False
        )
        p.require(
            saved_vectors["binding"]["inventory_id"] == inventory["id"]
            and saved_vectors["binding"]["full_G_id"] == full_G["id"],
            "reliability.original_gJ_vector_inventory_and_G_binding",
        )
        gradient_check = gradient_equivalence(gJ, saved_vectors["gJ"])
        c.write(
            directory / "gJ_equivalence.json",
            p.record("B_direction_reliability_gradient_check", **authority, **gradient_check),
        )
        p.require(gradient_check["passed"], "reliability.full_gJ_vector_equivalence_STOP")
        del saved_vectors
        pullback = old.adam.pullback(
            bound, population.G, {name: -value for name, value in gJ.items()}
        )
        binding = parent["materials"]["binding"]
        pi = binding["prior"]
        actual = population.centered(pi, binding["mu"], pullback["a"])
        geometry = direction.Geometry(
            population.keys, pi, pi, binding["mu"], binding["control_tasks"]
        )
        old_C = p.read_json(original / "C.json")["C"]
        old_pi = p.read_json(original / "distribution_update.json")["pi_next"]
        checks = {
            "original_gJ_full_vector": gradient_check,
            "original_GPU_replay_and_pullback": equivalence(
                geometry, geometry.flatten(actual["C"]), old_C, old_pi, len(inventory["positives"])
            ),
        }
        c.write(
            directory / "original_replay_equivalence.json",
            p.record(
                "B_direction_reliability_linkage_check",
                **authority,
                **checks["original_GPU_replay_and_pullback"],
            ),
        )
        p.require(
            checks["original_GPU_replay_and_pullback"]["passed"],
            "reliability.original_C_pi_replay_equivalence_STOP",
        )
        coefficients = original_linear_coefficients(old.adam, bound, population.G, population.names)
        flat_total = torch.cat(
            [gJ[name].detach().cpu().reshape(-1).double() for name in population.names]
        )
        total_projected = direction.project(
            population.matrix,
            cpu_linear_pullback(coefficients, -flat_total),
            population.keys,
            geometry,
        )[:, 0]
        checks["CPU_original_linear_operator_total"] = equivalence(
            geometry, total_projected, old_C, old_pi, len(inventory["positives"])
        )
        c.write(
            directory / "CPU_operator_equivalence.json",
            p.record(
                "B_direction_reliability_linkage_check",
                **authority,
                **checks["CPU_original_linear_operator_total"],
            ),
        )
        p.require(
            checks["CPU_original_linear_operator_total"]["passed"],
            "reliability.CPU_operator_equivalence_STOP",
        )
        projected = project_trajectories(
            c,
            directory / "responses",
            authority,
            inventory["responses"],
            inventory["positives"],
            population,
            coefficients,
            geometry,
        )
        checks["CPU_sum_of_unscaled_trajectory_projections"] = equivalence(
            geometry,
            projected.sum(axis=1) / DENOMINATOR,
            old_C,
            old_pi,
            len(inventory["positives"]),
        )
        numeric = p.record(
            "B_direction_reliability_equivalence",
            **authority,
            passed=all(row["passed"] for row in checks.values()),
            checks=checks,
            original_GPU_gJ_digest=old.gate.tensor_digest(gJ),
            original_saved_gJ_digest=p.read_json(original / "gJ.json")["gJ_digest"],
            no_stable_numeric_kernel_substitution=True,
        )
        c.write(directory / "equivalence.json", numeric)
        p.require(numeric["passed"], "reliability.trajectory_sum_C_pi_equivalence_STOP")
        analysis, vectors = mechanism_analysis(
            projected, inventory["positives"], parent["dev_tasks"], geometry
        )
        if not (directory / "vectors.pt").exists():
            c.s.atomic_torch(
                directory / "vectors.pt",
                dict(
                    kind="B_direction_reliability_vectors",
                    authority=authority,
                    keys=population.keys,
                    positives=inventory["positives"],
                    unscaled_trajectory_C=torch.from_numpy(projected),
                    **vectors,
                ),
            )
        old.adam._verify(bound)
        outer._restore_rng(c.b, saved)
        report = p.record(
            "B_direction_reliability_report",
            **authority,
            complete=True,
            equivalence_id=numeric["id"],
            equivalence_passed=True,
            accounting=dict(accounting),
            positive_trajectories=len(inventory["positives"]),
            zero_Q_terms_kept_in_denominators=True,
            new_G_passes=0,
            new_generation_calls=0,
            new_financial_assessments=0,
            actual_SFT_updates=0,
            trajectory_accumulator_dtype="CPU FP64 sum of original individual FP32 response gradients; no differencing of cumulative checkpoints",
            vectors_path=str(directory / "vectors.pt"),
            vectors_sha256=p.sha(directory / "vectors.pt"),
            original_kernel="FLASH_ATTENTION segmented_logp block_size=8; GPU FP32 response-ordered alpha=1/360",
            analysis=analysis,
            real_parameters_and_Adam_unchanged=True,
            prefix_RNG_restored=True,
        )
        c.write(existing, report)
        return report
    finally:
        old.adam._verify(bound)
        outer._restore_rng(c.b, saved)


def run(root, seed, attempt, required_MiB=51200):
    c = _common()
    try:
        with c.locked(
            c.RAW / "reliability" / f"B_direction_reliability_{seed}" / "worker.lock",
            blocking=False,
        ):
            return _run(c, Path(root), seed, attempt, required_MiB)
    finally:
        gc.collect()
        torch.cuda.empty_cache()
