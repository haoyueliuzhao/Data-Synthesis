"""V23 B: one distribution-only, equal-prior-KL shrink control per original seed.

The scientific runtime is supplied by the frozen V18 PYTHONPATH. This external
runner never estimates C, samples feedback, calls an API, or changes V18 records.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import fcntl
import hashlib
import json
import math
import os
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

SEEDS = (11, 29, 47)
MODEL = "deepseek-flash"
METRICS = ("execution_accuracy", "program_accuracy")
REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V18 = (
    REPO
    / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
    / "v18_researcher_continuation_01"
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def bound(value):
    return {**value, "id": digest(value)}


def read(path, *, content_id=True):
    value = json.loads(Path(path).read_bytes())
    if content_id:
        require(
            value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
            "source content ID changed: " + str(path),
        )
    return value


def entry(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(ref, *, content_id=True):
    require(
        entry(ref["path"]) == {k: ref[k] for k in ("path", "sha256")},
        "source bytes changed: " + ref["path"],
    )
    value = read(ref["path"], content_id=content_id)
    require("id" not in ref or value["id"] == ref["id"], "source identity changed")
    return value


def publish(path, value):
    from trusted_synthesis.finance_research.v8_training_driver import _publish

    _publish(Path(path), value)


def number(value):
    require(not isinstance(value, bool), "boolean is not a probability")
    value = float(Fraction(value)) if isinstance(value, str) else float(value)
    require(math.isfinite(value), "finite probabilities required")
    return value


def validate_distributions(qc, qn, prior, mu):
    require(
        set(qc) == set(qn) == set(prior) == set(mu) and qc, "unchanged full task support required"
    )
    weights = {t: number(v) for t, v in mu.items()}
    require(
        min(weights.values()) > 0 and math.isclose(math.fsum(weights.values()), 1, abs_tol=1e-12),
        "original normalized positive mu required",
    )
    distributions = []
    for source in (qc, qn, prior):
        converted = {}
        for t, row in source.items():
            require(set(row) == set(prior[t]) and row, "unchanged positive state support required")
            converted[t] = {z: number(v) for z, v in row.items()}
            require(
                min(converted[t].values()) > 0
                and math.isclose(math.fsum(converted[t].values()), 1, abs_tol=1e-12),
                "positive normalized conditional distributions required; no clipping",
            )
        distributions.append(converted)
    return (*distributions, weights)


def weighted_kl(q, reference, mu):
    return math.fsum(
        mu[t] * math.fsum(v * math.log(v / reference[t][z]) for z, v in row.items())
        for t, row in q.items()
    )


def geometric_shrink(qc, prior, gamma):
    require(math.isfinite(gamma) and 0 <= gamma <= 1, "gamma must remain in [0,1]")
    if gamma == 0:
        return copy.deepcopy(qc)
    if gamma == 1:
        return copy.deepcopy(prior)
    result = {}
    for t, row in qc.items():
        logs = {
            z: (1 - gamma) * math.log(v) + gamma * math.log(prior[t][z]) for z, v in row.items()
        }
        maximum = max(logs.values())
        mass = {z: math.exp(v - maximum) for z, v in logs.items()}
        total = math.fsum(mass.values())
        result[t] = {z: v / total for z, v in mass.items()}
    return result


def solve_gamma(qc, qn, prior, mu):
    """One scalar, fixed bisection; inputs deliberately exclude all model outcomes.

    With a=1-gamma, d KL(q_a||r)/da=a Var_q(log(qC/r)) >= 0.
    Thus the entire reachable range is exactly [0, KL(qC||r)].
    """
    qc, qn, prior, mu = validate_distributions(qc, qn, prior, mu)
    initial, target = weighted_kl(qc, prior, mu), weighted_kl(qn, prior, mu)
    feasible = 0 <= target <= initial
    result = dict(
        applicable=feasible,
        initial_KL_C_to_prior=initial,
        target_KL_N_to_prior=target,
        reachable_KL_interval=[0.0, initial],
        match_metric="mu-weighted KL(q||fixed prior)",
        gamma_domain=[0.0, 1.0],
        no_outcomes_NLL_or_trial_training_used=True,
    )
    if not feasible:
        return {
            **result,
            "gamma": None,
            "q_shrink": None,
            "reason": "target outside the fixed reachable interval; entire B branch not applicable",
        }
    lo, hi = 0.0, 1.0
    if target == initial:
        gamma = 0.0
    elif target == 0:
        gamma = 1.0
    else:
        for _ in range(80):
            mid = (lo + hi) / 2
            if weighted_kl(geometric_shrink(qc, prior, mid), prior, mu) > target:
                lo = mid
            else:
                hi = mid
        gamma = (lo + hi) / 2
    q = geometric_shrink(qc, prior, gamma)
    actual = weighted_kl(q, prior, mu)
    require(abs(actual - target) <= 1e-12, "fixed global KL match failed")
    return {
        **result,
        "gamma": gamma,
        "q_shrink": q,
        "matched_KL": actual,
        "residual": actual - target,
        "solver": "80 fixed bisection iterations; endpoints exact; no extrapolation",
    }


def all_seeds_applicable(seed_records):
    require(
        set(seed_records) == {str(s) for s in SEEDS}, "all three original seeds required; no subset"
    )
    return all(value["solution"]["applicable"] for value in seed_records.values())


def distribution_diagnostics(q, prior, current, qc, mu, chi):
    """Descriptive only. chi is the frozen process label, not actual semantic truth."""
    qc, q, prior, mu = validate_distributions(qc, q, prior, mu)
    current = {t: {z: number(v) for z, v in row.items()} for t, row in current.items()}
    rows = {}
    joint_hhi = 0.0
    quality_mass = 0.0
    quality_squared = 0.0
    for t, row in q.items():
        require(
            set(chi[t]) == set(row) and set(chi[t].values()) <= {0, 1, None},
            "frozen chi support required",
        )
        require(
            None not in chi[t].values() or (len(row) == 1 and set(chi[t].values()) == {None}),
            "unknown chi allowed only for registered deterministic singletons",
        )
        ratios = {z: v / prior[t][z] for z, v in row.items()}
        hhi = math.fsum(v * v for v in row.values())
        joint_hhi += mu[t] ** 2 * hhi
        good = math.fsum(v for z, v in row.items() if chi[t][z] == 1)
        quality_mass += mu[t] * good
        quality_squared += math.fsum((mu[t] * v) ** 2 for z, v in row.items() if chi[t][z] == 1)
        rows[t] = dict(
            q_over_r=ratios,
            KL_to_prior=math.fsum(v * math.log(ratios[z]) for z, v in row.items()),
            TV_to_prior=0.5 * math.fsum(abs(v - prior[t][z]) for z, v in row.items()),
            KL_to_current_anchor=math.fsum(v * math.log(v / current[t][z]) for z, v in row.items()),
            TV_to_current_anchor=0.5 * math.fsum(abs(v - current[t][z]) for z, v in row.items()),
            entropy=-math.fsum(v * math.log(v) for v in row.values()),
            conditional_HHI=hhi,
            conditional_ESS=1 / hhi,
            frozen_chi0_mass=math.fsum(v for z, v in row.items() if chi[t][z] == 0),
            frozen_chi_unknown_singleton_mass=math.fsum(
                v for z, v in row.items() if chi[t][z] is None
            ),
            frozen_chi0_net_mass_change_from_C=math.fsum(
                v - qc[t][z] for z, v in row.items() if chi[t][z] == 0
            ),
            frozen_chi0_positive_replenishment_from_C=math.fsum(
                max(0.0, v - qc[t][z]) for z, v in row.items() if chi[t][z] == 0
            ),
        )
        sets = {
            "current_anchor_below_prior": [z for z in row if current[t][z] < prior[t][z]],
            "C_below_prior": [z for z in row if qc[t][z] < prior[t][z]],
        }
        rows[t]["undercovered_states"] = sets
        for name, states in sets.items():
            rows[t].update(
                {
                    name + "_prior_mass": math.fsum(prior[t][z] for z in states),
                    name + "_current_anchor_mass": math.fsum(current[t][z] for z in states),
                    name + "_C_mass": math.fsum(qc[t][z] for z in states),
                    name + "_q_mass": math.fsum(row[z] for z in states),
                    name + "_net_replenishment_from_C": math.fsum(
                        row[z] - qc[t][z] for z in states
                    ),
                    name + "_positive_replenishment_from_C": math.fsum(
                        max(0.0, row[z] - qc[t][z]) for z in states
                    ),
                }
            )
    numeric = [k for k, v in next(iter(rows.values())).items() if isinstance(v, (int, float))]
    return dict(
        per_task=rows,
        mu_weighted={k: math.fsum(mu[t] * row[k] for t, row in rows.items()) for k in numeric},
        global_q_over_r_minimum=min(v for r in rows.values() for v in r["q_over_r"].values()),
        global_q_over_r_maximum=max(v for r in rows.values() for v in r["q_over_r"].values()),
        joint_task_state_HHI=joint_hhi,
        joint_task_state_ESS=1 / joint_hhi,
        frozen_chi1_joint_mass=quality_mass,
        chi1_renormalized_joint_HHI=None
        if quality_mass == 0
        else quality_squared / quality_mass**2,
        chi1_renormalized_joint_ESS=None
        if quality_squared == 0
        else quality_mass**2 / quality_squared,
        undercoverage_semantics=(
            "probability mass below fixed prior, separately at actual pre-outer current anchor "
            "and post-C distribution; no quality label or model outcome used"
        ),
        quality_label_semantics=(
            "frozen process chi labels; unknown deterministic singletons stay separate, "
            "never chi0/chi1; not objective quality adjudication"
        ),
    )


def verify_reused_point(source_root, mechanism_reg, build, seed, condition, sources):
    root = Path(source_root) / f"mechanisms/seed{seed}/evaluation/N_same_point/{condition}"

    def source(path):
        sources[str(path.resolve())] = entry(path)
        return read(path)

    score = source(root / "scores/record.json")
    seal = source(root / "whole_seal/record.json")
    intent = source(root / "intent/record.json")
    ref = build["conditions"][condition]
    coordinates = [f"draw{i}/{t}" for i in range(3) for t in mechanism_reg["calibration_task_ids"]]
    require(
        all(
            v["checkpoint"] == ref
            and v["seed"] == seed
            and v["condition"] == condition
            and v["denominator"] == 360
            and v["registration_id"] == mechanism_reg["id"]
            for v in (score, seal, intent)
        ),
        "reused N checkpoint/seed/condition mismatch",
    )
    require(
        score["seal_id"] == seal["id"]
        and seal["mechanism_result_id"] == intent["mechanism_result_id"] == build["id"]
        and score["unknown"] == 0
        and [r["coordinate"] for r in score["rows"]] == coordinates,
        "reused N score/seal/coordinates mismatch",
    )
    require(
        [r["episode_sha256"] for r in score["rows"]] == seal["episode_sha256"],
        "reused N score episodes differ",
    )
    for i, config in enumerate(mechanism_reg["evaluation_configs"]):
        run = source(root / f"draw{i}/run.json")
        draw_seal = source(root / f"draw{i}/generation_seal/seal.json")
        require(
            run["config"] == config
            and run["tasks"] == mechanism_reg["calibration_task_keys"]
            and run["provider"] == intent["identity"]
            and run["registered_denominator"] == 120
            and run["runtime_binding"] == mechanism_reg["runtime_binding"],
            "reused N execution configuration changed",
        )
        require(
            draw_seal["id"] == seal["draw_seal_ids"][i]
            and draw_seal["run_id"] == run["id"]
            and draw_seal["complete"]
            and draw_seal["all_provider_calls_settled"],
            "reused N draw not complete",
        )
    stratify(score["rows"], mechanism_reg["calibration_task_ids"])
    return entry(root / "scores/record.json")


def prepare(root, source_root=V18):
    """Immutable CPU preparation. No model, tensor, private-reference or API reads."""
    from trusted_synthesis.finance_research.storage import runtime_binding
    from trusted_synthesis.finance_research.v9_mechanism_execution import evaluation_configs

    root, source_root = Path(root).resolve(), Path(source_root).resolve()
    require(not root.exists(), "new B branch root required; never overwrite or retune gamma")
    sources = {}

    def source(path, *, content_id=True):
        path = Path(path).resolve()
        sources[str(path)] = entry(path)
        return read(path, content_id=content_id)

    reg = source(source_root / "mechanisms/registration/record.json")
    plan = source(Path(reg["launcher"]) / "registration/record.json")
    require(
        reg["runtime_binding"] == plan["runtime_binding"] == runtime_binding(),
        "use the frozen original scientific runtime",
    )
    require(
        reg["seeds"] == list(SEEDS) and plan["id"] == reg["launcher_id"],
        "original three seeds and launcher required",
    )
    configs = [c.model_dump(mode="json") for c in evaluation_configs()]
    require(
        reg["evaluation_configs"] == configs and all(c["api_model"] == MODEL for c in configs),
        "original calibration execution and deepseek-flash field required",
    )
    require(
        len(reg["calibration_task_ids"]) == len(set(reg["calibration_task_ids"])) == 120,
        "fixed calibration120 required",
    )
    material = checked(plan["material_binding"])
    sources[plan["material_binding"]["path"]] = plan["material_binding"]
    support = checked(material["support_manifest"])
    sources[material["support_manifest"]["path"]] = material["support_manifest"]
    require(
        support["execution_plan"] == reg["execution_plan"]
        and support["N"] == 744
        and set(support["mu"]) == set(support["training_task_ids"])
        and all(v == reg["execution_plan"]["mu"] for v in support["mu"].values()),
        "original support/explicit task mu changed",
    )
    mu = support["mu"]
    chi = {t: v["chi"] for t, v in support["task_support"].items()}
    seeds = {}
    for seed in SEEDS:
        build = source(source_root / f"mechanisms/seed{seed}/N_same_point/result/record.json")
        cbuild = source(source_root / f"mechanisms/seed{seed}/C_direction/result/record.json")
        outer = source(Path(build["source_outer"]["path"]) / "record.json", content_id=False)
        previous = source(
            Path(build["source_outer"]["path"]).parent / "step0298_outer/record.json",
            content_id=False,
        )
        require(
            build["pool_id"] == cbuild["pool_id"] == reg["pool_id"] == outer["pool_id"]
            and build["seed"] == cbuild["seed"] == seed
            and build["start_step"] == 596
            and build["end_step"] == 745,
            "same-point registered pool/seed/interval changed",
        )
        require(
            outer["state_sha256"] == build["source_outer"]["state_sha256"]
            and outer["actual_state_digest"] == build["source_outer"]["actual_state_digest"]
            and outer["outer_inputs_digest"] == build["arithmetic"]["actual_outer_inputs_digest"]
            and outer["step"] == 596
            and outer["arm"] == "C-only",
            "actual saved C outer identity changed",
        )
        qc, qn, prior = build["arithmetic"]["C_only"], build["arithmetic"]["Full"], cbuild["prior"]
        require(
            outer["evidence"]["distribution"]["pi_next"] == qc
            and previous["step"] == 298
            and previous["arm"] == "C-only"
            and previous["pool_id"] == reg["pool_id"],
            "saved C distributions changed",
        )
        current = previous["evidence"]["distribution"]["pi_next"]
        solution = solve_gamma(qc, qn, prior, mu)
        diagnostics = {
            k: distribution_diagnostics(q, prior, current, qc, mu, chi)
            for k, q in {
                "C-only": qc,
                "Full-N": qn,
                **({"shrink": solution["q_shrink"]} if solution["applicable"] else {}),
            }.items()
        }
        reused = {
            c: verify_reused_point(source_root, reg, build, seed, c, sources)
            for c in ("C-only", "Full")
        }
        seeds[str(seed)] = dict(
            seed=seed,
            solution=solution,
            diagnostics=diagnostics,
            source_outer=build["source_outer"],
            source_outer_record=entry(Path(build["source_outer"]["path"]) / "record.json"),
            actual_outer_inputs_digest=build["arithmetic"]["actual_outer_inputs_digest"],
            q_C=qc,
            q_N=qn,
            prior=prior,
            current_anchor=current,
            reused_N_scores=reused,
            old_N_result_id=build["id"],
        )
    applicable = all_seeds_applicable(seeds)
    value = bound(
        dict(
            schema="v23_equal_prior_KL_shrink_registration.v1",
            source_root=str(source_root),
            source_mechanism_registration_id=reg["id"],
            launcher=reg["launcher"],
            launcher_id=plan["id"],
            pool_id=reg["pool_id"],
            runtime_binding=reg["runtime_binding"],
            source_files=sources,
            implementation=entry(__file__),
            seeds=list(SEEDS),
            seed_records=seeds,
            applicable=applicable,
            mu=mu,
            chi=chi,
            calibration_task_ids=reg["calibration_task_ids"],
            calibration_task_keys=reg["calibration_task_keys"],
            evaluation_configs=configs,
            model=MODEL,
            API_calls=0,
            new_feedback_sessions=0,
            start_step=596,
            end_step=745,
            new_training_steps=447 if applicable else 0,
            new_evaluation_denominator=1080 if applicable else 0,
            reused_evaluation_denominator=2160,
            primary_deployment_estimand=(
                "greedy native execution accuracy; program accuracy secondary"
            ),
            stochastic_estimand=(
                "mean correctness over two original independent draws; not best-of-two"
            ),
            old_mixed_estimand_unchanged=True,
            calibration_previously_exposed=True,
            statistical_significance_claimed=False,
            matching_scope=(
                "only global mu-weighted KL to fixed prior; per-task KL, TV, entropy "
                "and current-anchor distances are not matched"
            ),
            no_seed_deletion_or_metric_switch=True,
            no_hyperparameter_or_checkpoint_selection=True,
        )
    )
    publish(root / "registration", value)
    if not applicable:
        publish(
            root / "evaluation_result",
            bound(
                dict(
                    schema="v23_shrink_not_applicable.v1",
                    registration_id=value["id"],
                    applicable=False,
                    reason=(
                        "at least one original seed outside reachable KL interval; no seed dropped"
                    ),
                    API_calls=0,
                )
            ),
        )
    return value


def registration(root, *, verify_sources=False):
    from trusted_synthesis.finance_research.storage import runtime_binding

    reg = read(Path(root) / "registration/record.json")
    require(
        reg["model"] == MODEL and reg["API_calls"] == 0 and reg["new_feedback_sessions"] == 0,
        "API disabled and model must be deepseek-flash",
    )
    require(
        reg["runtime_binding"] == runtime_binding() and reg["implementation"] == entry(__file__),
        "frozen B implementation/scientific runtime changed",
    )
    require(reg["seeds"] == list(SEEDS), "all original seeds required")
    require(
        reg["applicable"] == all_seeds_applicable(reg["seed_records"]),
        "B applicability cannot select a seed subset",
    )
    if verify_sources:
        for ref in reg["source_files"].values():
            require(entry(ref["path"])["sha256"] == ref["sha256"], "B source changed")
    return reg


@contextmanager
def locked(root, name):
    path = Path(root) / "locks"
    path.mkdir(exist_ok=True)
    with (path / (name + ".lock")).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def execute_shrink(*, factory, source_outer, spec, output):
    """Actual model/Adam/RNG restore and one fixed epoch; usable with tiny CPU tests."""
    import torch

    from trusted_synthesis.finance_research.v8_training_driver import _sha, _tree_digest
    from trusted_synthesis.finance_research.v9_mechanism_execution import (
        _validate_interval,
        checkpoint,
        checkpoint_ref,
    )

    output = Path(output)
    require(not output.exists(), "existing shrink training must not be repeated")
    record, state = checkpoint(source_outer)
    actual_path = Path(source_outer) / "outer_inputs.pt"
    require(
        _sha(actual_path.read_bytes()) == record["outer_inputs_sha256"],
        "actual saved outer tensors changed",
    )
    actual = torch.load(actual_path, map_location="cpu", weights_only=False)
    require(
        _tree_digest(actual) == record["outer_inputs_digest"] == spec["actual_outer_inputs_digest"],
        "saved outer input identity changed",
    )
    before = actual["pre_state"]
    trial = factory(output / "training", "C-only")
    start, stop = (
        4 * trial.execution_plan["steps_per_epoch"],
        5 * trial.execution_plan["steps_per_epoch"],
    )
    require(
        state["arm"] == "C-only"
        and state["step"] == start
        and state["seed"] == trial.seed
        and state["pool_id"] == trial.pool.cache_id
        and state["pi"] == spec["q_C"]
        and state["prior"] == before["prior"] == spec["prior"]
        and before["pi"] == spec["current_anchor"]
        and actual["mu"] == spec["mu"],
        "exact original C point/distributions/mu required",
    )
    for key in (
        "parameters",
        "buffers",
        "optimizer",
        "rng",
        "frozen_base_digest",
        "adapter_binding",
        "schedule",
    ):
        require(
            _tree_digest(state[key]) == _tree_digest(before[key]),
            "outer must preserve actual theta/Adam/RNG/schedule: " + key,
        )
    require(
        start in state["outer_done"] and all(not start < s < stop for s in trial.outer_steps),
        "interval must contain no new outer feedback",
    )
    require(spec["solution"]["applicable"], "unmatched seed cannot be trained")
    q = spec["solution"]["q_shrink"]
    trial.restore(source_outer)
    trial.pi = copy.deepcopy(q)
    trial.commit(
        "mechanism_branch",
        dict(
            mechanism="equal_prior_KL_shrink",
            source_outer=checkpoint_ref(source_outer),
            gamma=spec["solution"]["gamma"],
            no_new_feedback=True,
            original_current=before["pi"],
            unchanged_prior=before["prior"],
            main_C_only=False,
        ),
    )
    trial.run_until(stop)
    final = _validate_interval(trial.root, start, stop, q, before)
    result = bound(
        dict(
            schema="v23_actual_shrink_short_training.v1",
            seed=trial.seed,
            pool_id=trial.pool.cache_id,
            start_step=start,
            end_step=stop,
            actual_extra_training_steps=stop - start,
            source_outer=checkpoint_ref(source_outer),
            checkpoint=final,
            gamma=spec["solution"]["gamma"],
            q_shrink=q,
            actual_outer_inputs_digest=spec["actual_outer_inputs_digest"],
            actual_G_gJ_C_reused=True,
            prior_changed=False,
            new_feedback_sessions=0,
            API_calls=0,
            internal_consumer_arm="C-only",
            is_main_C_only=False,
            actual_production_training=trial.pool.production_verified,
            actual_GPU_training=trial.pool.production_verified
            and str(trial.device).startswith("cuda"),
        )
    )
    publish(output / "result", result)
    return result


def choose_gpu(plan, gpu_index):
    import torch

    from trusted_synthesis.finance_research.v9_training_launcher import eligible_gpu, gpu_inventory

    row = eligible_gpu(plan, gpu_index, gpu_inventory())
    require(not torch.cuda.is_initialized(), "fresh process required for explicit GPU mapping")
    os.environ["CUDA_VISIBLE_DEVICES"] = row["uuid"]
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")


def train(root, seed, gpu_index):
    from trusted_synthesis.finance_research.v9_conditional_training import ConditionalTrainingDriver
    from trusted_synthesis.finance_research.v9_training_launcher import (
        _load_components,
        checked_launch,
    )

    root = Path(root).resolve()
    with locked(root, f"train-{seed}"):
        reg = registration(root, verify_sources=True)
        require(reg["applicable"] and seed in SEEDS, "B not applicable or foreign seed")
        plan, pool, assets = checked_launch(reg["launcher"])
        require(
            plan["id"] == reg["launcher_id"] and pool.cache_id == reg["pool_id"],
            "launcher/material changed",
        )
        require(not (root / f"seed{seed}").exists(), "no automatic restart or retraining")
        choose_gpu(plan, gpu_index)
        model, tokenizer, optimizer, scope, _ = _load_components(assets, seed)

        def factory(path, arm):
            return ConditionalTrainingDriver(
                model,
                optimizer,
                pool,
                root=path,
                seed=seed,
                arm=arm,
                device="cuda:0",
                tokenizer=tokenizer,
                adapter_scope=scope,
            )

        spec = {**reg["seed_records"][str(seed)], "mu": reg["mu"]}
        return execute_shrink(
            factory=factory,
            source_outer=spec["source_outer"]["path"],
            spec=spec,
            output=root / f"seed{seed}",
        )


def point(root, seed):
    from trusted_synthesis.finance_research.v9_mechanism_execution import checkpoint, checkpoint_ref

    root = Path(root).resolve()
    reg = registration(root)
    require(reg["applicable"] and seed in SEEDS, "B not applicable or foreign seed")
    result = read(root / f"seed{seed}/result/record.json")
    spec = reg["seed_records"][str(seed)]
    ref = result["checkpoint"]
    require(
        result["seed"] == seed
        and result["pool_id"] == reg["pool_id"]
        and result["source_outer"] == spec["source_outer"]
        and result["gamma"] == spec["solution"]["gamma"]
        and result["q_shrink"] == spec["solution"]["q_shrink"],
        "trained B point differs from fixed gamma/source",
    )
    require(checkpoint_ref(ref["path"]) == ref, "B checkpoint changed")
    _, state = checkpoint(ref["path"])
    require(
        state["step"] == 745
        and state["pi"] == result["q_shrink"]
        and state["pool_id"] == reg["pool_id"],
        "B endpoint changed",
    )
    plan = read(Path(reg["launcher"]) / "registration/record.json")
    require(plan["id"] == reg["launcher_id"], "source launcher changed")
    assets = checked(plan["assets_protocol"])
    return reg, plan, assets, result, ref, state, root / f"seed{seed}/evaluation"


def generate(root, seed, gpu_index):
    from trusted_synthesis.finance_research.contracts import RunConfig
    from trusted_synthesis.finance_research.providers import (
        LocalTorchProvider,
        local_model_identity,
    )
    from trusted_synthesis.finance_research.storage import execute_run, prepare_run
    from trusted_synthesis.finance_research.v9_final_evaluation import install_checkpoint_state
    from trusted_synthesis.finance_research.v9_training_launcher import _load_components

    with locked(root, f"generate-{seed}"):
        reg, plan, assets, result, ref, state, target = point(root, seed)
        require(not target.exists(), "existing B generation cannot be resampled")
        choose_gpu(plan, gpu_index)
        model, tokenizer, _, scope, _ = _load_components(assets, seed)
        parameters = install_checkpoint_state(model, state, scope)
        identity = local_model_identity(
            model,
            tokenizer,
            model_id=assets["assets"]["base_binding"]["id"],
            point_id="v23-shrink:" + digest(dict(registration=reg["id"], reference=ref)),
            parameter_tensors=parameters,
        )
        provider = LocalTorchProvider(model, tokenizer, identity, parameter_tensors=parameters)
        publish(
            target / "intent",
            bound(
                dict(
                    registration_id=reg["id"],
                    mechanism_result_id=result["id"],
                    checkpoint=ref,
                    identity=identity.model_dump(mode="json"),
                    seed=seed,
                    denominator=360,
                    private_references_read=False,
                )
            ),
        )
        for index, config in enumerate(reg["evaluation_configs"]):
            require(config["api_model"] == MODEL, "API model must be deepseek-flash; no fallback")
            path = target / f"draw{index}"
            prepare_run(
                assets["snapshot"],
                assets["role_plan"],
                path,
                role="calibration",
                config=RunConfig.model_validate(config),
                identity=identity,
                task_keys=reg["calibration_task_keys"],
            )
            asyncio.run(execute_run(path, provider))
        return seal(root, seed)


def seal(root, seed):
    from trusted_synthesis.finance_research.contracts import digest as object_digest
    from trusted_synthesis.finance_research.storage import sealed_episodes

    reg = registration(root)
    target = Path(root) / f"seed{seed}/evaluation"
    result = read(Path(root) / f"seed{seed}/result/record.json")
    intent = read(target / "intent/record.json")
    require(
        intent["checkpoint"] == result["checkpoint"]
        and intent["mechanism_result_id"] == result["id"]
        and intent["registration_id"] == reg["id"],
        "B intent changed",
    )
    episodes, seals = [], []
    for index, config in enumerate(reg["evaluation_configs"]):
        run, draw_seal, part = sealed_episodes(target / f"draw{index}")
        require(
            run["tasks"] == reg["calibration_task_keys"]
            and run["config"] == config
            and run["provider"] == intent["identity"]
            and [e.task_id for e in part] == reg["calibration_task_ids"]
            and all(e.all_provider_calls_settled for e in part),
            "all original calibration draws required",
        )
        episodes.extend(part)
        seals.append(draw_seal["id"])
    require(len(episodes) == 360, "fixed360 before private reference access")
    value = bound(
        dict(
            schema="v23_shrink_whole_point_seal.v1",
            registration_id=reg["id"],
            mechanism_result_id=result["id"],
            checkpoint=result["checkpoint"],
            seed=seed,
            denominator=360,
            draw_seal_ids=seals,
            episode_sha256=[object_digest(e) for e in episodes],
            private_references_read=False,
        )
    )
    publish(target / "whole_seal", value)
    return value


def stratify(rows, task_ids):
    coordinates = [f"draw{i}/{t}" for i in range(3) for t in task_ids]
    require(
        len(task_ids) == 120
        and len(set(task_ids)) == 120
        and [r["coordinate"] for r in rows] == coordinates,
        "complete ordered360 outcomes required",
    )
    output = {}
    for metric in METRICS:
        values = [r["native"]["native"][metric] for r in rows]
        require(
            all(type(v) in (int, float) and v in (0, 1) for v in values),
            "unknown/nonbinary scores cannot become failure",
        )
        output[metric] = {
            name: dict(
                correct=sum(values[i] for i in indices),
                denominator=len(indices),
                mean=math.fsum(values[i] for i in indices) / len(indices),
            )
            for name, indices in {
                "greedy": list(range(240, 360)),
                "stochastic_expectation": list(range(240)),
                "draw0": list(range(120)),
                "draw1": list(range(120, 240)),
                "legacy_mixed_descriptive": list(range(360)),
            }.items()
        }
    return output


def score(root):
    """All1080 new generations sealed before the first private-reference read."""
    from trusted_synthesis.finance_research.contracts import (
        PrivateReference,
        TaskBundle,
    )
    from trusted_synthesis.finance_research.contracts import (
        digest as object_digest,
    )
    from trusted_synthesis.finance_research.storage import (
        _read_snapshot_rows,
        load_public_snapshot,
        sealed_episodes,
    )
    from trusted_synthesis.finance_research.v6_task import score_public_reasoning_program

    root = Path(root).resolve()
    with locked(root, "score"):
        reg = registration(root, verify_sources=True)
        require(reg["applicable"], "B not applicable")
        seals = {seed: seal(root, seed) for seed in SEEDS}
        require(
            sum(s["denominator"] for s in seals.values()) == 1080,
            "all1080 before private references",
        )
        plan = read(Path(reg["launcher"]) / "registration/record.json")
        assets = checked(plan["assets_protocol"])
        manifest, public, lineages = load_public_snapshot(assets["snapshot"])
        references = _read_snapshot_rows(
            assets["snapshot"], "private.references.jsonl", PrivateReference, manifest
        )
        bundles = {
            t.task_id: TaskBundle(public=t, reference=r, lineage=lineage)
            for t, r, lineage in zip(public, references, lineages, strict=True)
        }
        seed_results = {}
        for seed in SEEDS:
            rows = []
            target = root / f"seed{seed}/evaluation"
            for index in range(3):
                _, _, episodes = sealed_episodes(target / f"draw{index}")
                for episode in episodes:
                    rows.append(
                        dict(
                            coordinate=f"draw{index}/{episode.task_id}",
                            task_id=episode.task_id,
                            draw=index,
                            episode_sha256=object_digest(episode),
                            native=score_public_reasoning_program(
                                bundles[episode.task_id], episode
                            ),
                        )
                    )
            strata = stratify(rows, reg["calibration_task_ids"])
            value = bound(
                dict(
                    schema="v23_shrink_native_scores.v1",
                    registration_id=reg["id"],
                    seal_id=seals[seed]["id"],
                    seed=seed,
                    checkpoint=seals[seed]["checkpoint"],
                    denominator=360,
                    rows=rows,
                    strata=strata,
                    unknown_as_zero=False,
                )
            )
            publish(target / "scores", value)
            reused = {
                c: checked(ref)
                for c, ref in reg["seed_records"][str(seed)]["reused_N_scores"].items()
            }
            groups = {
                "shrink": strata,
                **{c: stratify(v["rows"], reg["calibration_task_ids"]) for c, v in reused.items()},
            }
            comparisons = {}
            for metric in METRICS:
                comparisons[metric] = {}
                for stratum, draws in (
                    ("greedy", {2}),
                    ("stochastic_expectation", {0, 1}),
                    ("legacy_mixed_descriptive", {0, 1, 2}),
                ):
                    comparisons[metric][stratum] = {}
                    all_rows = {"shrink": rows, **{c: v["rows"] for c, v in reused.items()}}
                    for name, left, right in (
                        ("shrink-C-only", "shrink", "C-only"),
                        ("Full-shrink", "Full", "shrink"),
                        ("Full-C-only", "Full", "C-only"),
                    ):
                        delta = [
                            a["native"]["native"][metric] - b["native"]["native"][metric]
                            for a, b in zip(all_rows[left], all_rows[right], strict=True)
                            if a["draw"] in draws
                        ]
                        comparisons[metric][stratum][name] = dict(
                            difference=math.fsum(delta) / len(delta),
                            wins=sum(x > 0 for x in delta),
                            losses=sum(x < 0 for x in delta),
                            ties=sum(x == 0 for x in delta),
                            denominator=len(delta),
                        )
            seed_results[str(seed)] = dict(
                groups=groups, comparisons=comparisons, score_id=value["id"]
            )
        means = {
            metric: {
                stratum: {
                    name: math.fsum(
                        seed_results[str(s)]["comparisons"][metric][stratum][name]["difference"]
                        for s in SEEDS
                    )
                    / 3
                    for name in ("shrink-C-only", "Full-shrink", "Full-C-only")
                }
                for stratum in ("greedy", "stochastic_expectation", "legacy_mixed_descriptive")
            }
            for metric in METRICS
        }
        value = bound(
            dict(
                schema="v23_shrink_evaluation_result.v1",
                registration_id=reg["id"],
                applicable=True,
                seeds=seed_results,
                mean_differences=means,
                new_denominator=1080,
                reused_denominator=2160,
                new_training_steps=447,
                all_new_generation_before_scoring=True,
                old_mixed_result_unchanged=True,
                exposed_calibration_diagnostic_only=True,
                statistical_significance_claimed=False,
                matched_only_global_prior_KL=True,
                API_calls=0,
                new_feedback_sessions=0,
            )
        )
        publish(root / "evaluation_result", value)
        return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "train", "generate", "score"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=V18)
    parser.add_argument("--seed", type=int, choices=SEEDS)
    parser.add_argument("--gpu-index", type=int)
    args = parser.parse_args(argv)
    if args.action == "prepare":
        result = prepare(args.root, args.source_root)
    elif args.action == "score":
        result = score(args.root)
    else:
        require(args.seed is not None and args.gpu_index is not None, "seed and GPU index required")
        result = {"train": train, "generate": generate}[args.action](
            args.root, args.seed, args.gpu_index
        )
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("id", "schema", "applicable", "seed", "denominator", "new_denominator")
                if k in result
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
