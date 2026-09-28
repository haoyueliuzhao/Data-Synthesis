"""Register the independently authorized new full Probe batch, never splice stock.

Registration is not model execution. The current decomposition technical gate is
bound explicitly and must pass before a separate launch admission is recorded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from .calibration import ROOT, now, publish
from .contracts import RunConfig, digest
from .harness import episode_tool_specs, system_message
from .planning import task_key, verify_role_plan
from .probe_budget import ProbePriceSheet
from .profiles import public_run_view
from .storage import load_public_snapshot, read_json, runtime_binding
from .v6_collection import STUDY, bound, require, sha
from .v6_decomposed_review import job_directory
from .v6_review_revision import connect, original_protocol, paid_row

OUTPUT = STUDY / "new_full_probe_v7_01"
REVIEW_COHORT = STUDY / "review_revision_04"
HARNESS, PROFILE = "bigfinance-derived-vtdo-v7", "finqa-public-reasoning-v2"


def public_capacity(task):
    """Public-only size rule, identical for all eight slots; no native-score input."""
    chars = len(task.question)
    cells = 0
    for source in task.sources:
        if isinstance(source.content, str):
            chars += len(source.content)
        else:
            for row in source.content:
                cells += len(row)
                chars += sum(len(cell) for cell in row)
    cap = 16384 if chars > 8000 or cells > 200 else 2048
    return dict(
        public_text_chars=chars,
        table_cells=cells,
        max_new_tokens=cap,
        rule="16384 if public text >8000 chars or table >200 cells; otherwise2048",
        actual_output_token_prediction=False,
        uses_reference_or_old_success=False,
    )


def historical_prefix(review_cohort=REVIEW_COHORT):
    review_cohort = Path(review_cohort)
    parent = read_json(review_cohort / "registration/protocol.json")
    require(
        parent["id"] == digest({k: v for k, v in parent.items() if k != "id"}),
        "review cohort protocol changed",
    )
    # Registration is read-only design work. Do not use the old run's recovery
    # validator here: a corrected host validator must not replace its immutable
    # original assessments or pretend that an UNKNOWN request was settled.
    review_records = []
    for job in parent.get("jobs", []):
        directory = job_directory(review_cohort, job)
        response, assessment = (
            directory / "response/record.json",
            directory / "assessment/record.json",
        )
        if response.exists():
            require(assessment.exists(), "returned review is missing its original assessment")
            review_records.append(
                dict(
                    job_key=job["key"],
                    response_sha256=sha(response),
                    original_assessment_sha256=sha(assessment),
                )
            )
    gate = read_json(review_cohort / "technical_gate/record.json")
    require(
        gate["id"] == digest({k: v for k, v in gate.items() if k != "id"})
        and gate["protocol_id"] == parent["id"],
        "review admission identity changed",
    )
    price = ProbePriceSheet(**parent["budget"]["price_sheet"])
    with connect() as con:
        halt_row = con.execute("SELECT value FROM metadata WHERE key='halt'").fetchone()
        halt = json.loads(halt_row[0]) if halt_row else None
        config = json.loads(
            con.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        rows, unknown = [], []
        for row in con.execute("SELECT * FROM requests ORDER BY invocation_id"):
            if row["state"] == "SETTLED":
                rows.append(paid_row(row, price)[0])
                continue
            require(
                row["state"] == "UNKNOWN", "active pending call prevents quiescent registration"
            )
            require(
                row["usage_json"] is None and row["settled_microcny"] is None,
                "unknown usage must not be fabricated or called settled",
            )
            require(
                hashlib.sha256(row["request_body"]).hexdigest() == row["request_sha256"],
                "unknown original request bytes changed",
            )
            coordinates = json.loads(row["coordinates_json"])
            unknown.append(
                dict(
                    invocation_id=row["invocation_id"],
                    episode_id=coordinates["episode_id"],
                    state="UNKNOWN",
                    request_sha256=row["request_sha256"],
                    response_sha256=row["response_sha256"],
                    reserved_microcny=row["reserved_microcny"],
                    settled_microcny=None,
                    usage_known=False,
                    retry_authorized=False,
                )
            )
        counters = dict(con.execute("SELECT * FROM counters WHERE singleton=1").fetchone())
    require(
        all(
            config.get(k) == parent["budget"].get(k)
            for k in (
                "run_id",
                "purpose",
                "price_sheet",
                "hard_cap_microcny",
                "warning_microcny",
                "request_cap",
            )
        )
        and config["hard_cap_microcny"] == 800_000_000
        and config["warning_microcny"] == 700_000_000
        and config["request_cap"] == 258000
        and config["amendment_id"] == parent["budget"]["amendment_id"]
        and config["allowed_output_limits"] == parent["allowed_output_limits"],
        "original joint budget configuration changed; no new or higher cap authorized",
    )
    require(
        counters["spent"] == sum(r["settled_microcny"] for r in rows)
        and counters["requests"] == len(rows) + len(unknown)
        and counters["held"] == sum(r["reserved_microcny"] for r in unknown)
        and counters["pending"] == 0
        and counters["unknown"] == len(unknown),
        "all settled costs and unknown reservations must remain conserved",
    )
    return bound(
        dict(
            at=now(),
            review_protocol_id=parent["id"],
            review_gate=gate,
            review_gate_sha256=sha(review_cohort / "technical_gate/record.json"),
            review_cohort_directory=str(review_cohort),
            completed_decomposed_reviews=len(review_records),
            original_review_records=review_records,
            ledger_config=config,
            ledger_config_sha256=digest(config),
            counters=counters,
            paid_entries=rows,
            unknown_entries=unknown,
            budget_halt=halt,
            paid_execution_requires_separate_admission=True,
            unknown_costs_not_relabelled_as_settled=True,
            no_old_call_or_charge_removed=True,
        )
    )


def build_plan(source_commit, history):
    old = original_protocol()
    manifest, tasks, lineages = load_public_snapshot(old["snapshot"])
    verify_role_plan(old["role_plan"], tasks, lineages)
    original = [t for t in tasks if old["role_plan"]["assignments"][task_key(t)] == "sft"]
    require(
        len(original) == 1000
        and [t.task_id for t in original] == old["task_ids"]
        and manifest["id"] == old["snapshot_id"],
        "new full population must remain original1000",
    )
    config_by_task, capacities = {}, {}
    for task in original:
        capacity = public_capacity(task)
        config = RunConfig(
            harness_id=HARNESS,
            submission_profile=PROFILE,
            role="sft",
            temperature=1,
            max_steps=32,
            max_new_tokens=capacity["max_new_tokens"],
            context_limit=1048576,
        )
        config_by_task[task.task_id] = config.model_dump(mode="json")
        capacities[task.task_id] = {
            **capacity,
            "public_view_sha256": digest(public_run_view(task, PROFILE)),
        }
    sample = RunConfig.model_validate(config_by_task[original[0].task_id])
    scope = digest(
        dict(
            source_commit=source_commit,
            original_snapshot=manifest["id"],
            profile=PROFILE,
            configs=config_by_task,
            independent_new_batch=True,
        )
    )
    slots = [
        dict(
            task_id=t.task_id,
            slot_index=i,
            purpose="common_material_candidate",
            slot_id="v7-slot:" + digest(dict(scope=scope, task_id=t.task_id, slot_index=i)),
        )
        for t in original
        for i in range(8)
    ]
    old_slots = {s["slot_id"] for s in old["inventory"]["slots"]}
    require(
        not old_slots & {s["slot_id"] for s in slots},
        "old and new slot identities must be disjoint",
    )
    cfg = history["ledger_config"]
    counter = history["counters"]
    body = dict(
        schema="finqa_v7_new_full_probe.v1",
        at=now(),
        source_commit=source_commit,
        runtime_binding=runtime_binding(),
        authorization="设计并登记新一整批轨迹，保留旧批，不按成绩拼接",
        original_snapshot=old["snapshot"],
        snapshot_id=manifest["id"],
        role_plan=old["role_plan"],
        task_ids=old["task_ids"],
        task_denominator=1000,
        slots_per_task=8,
        slot_denominator=8000,
        all_eight_common_candidates=True,
        slots=slots,
        configs_by_task=config_by_task,
        public_capacity_by_task=capacities,
        capacity_histogram=dict(Counter(c["max_new_tokens"] for c in capacities.values())),
        public_system=system_message(sample),
        public_tools=episode_tool_specs(sample),
        launch_order="slot index first, then original task order; not prior grades",
        sampling=dict(
            model="deepseek-flash",
            thinking="disabled",
            temperature=1,
            top_p=1,
            seed_sent=False,
            max_steps=32,
            concurrent_episodes=16,
            unsupported_parallel_tool_calls_parameter_sent=False,
            wrong_multiple_calls_preserved_not_split_or_repaired=True,
        ),
        prior_original_protocol_id=old["id"],
        historical_audit_id=history["id"],
        budget=dict(
            run_id=cfg["run_id"],
            purpose=cfg["purpose"],
            amendment_id=cfg["amendment_id"],
            price_sheet=cfg["price_sheet"],
            hard_cap_microcny=cfg["hard_cap_microcny"],
            warning_microcny=cfg["warning_microcny"],
            request_cap=cfg["request_cap"],
            allowed_output_limits=cfg["allowed_output_limits"],
            inherited_spent_microcny=counter["spent"],
            inherited_held_microcny=counter.get("held", 0),
            inherited_unknown_requests=counter.get("unknown", 0),
            inherited_requests=counter["requests"],
            remaining_cost_microcny=cfg["hard_cap_microcny"]
            - counter["spent"]
            - counter.get("held", 0),
            remaining_request_budget=cfg["request_cap"] - counter["requests"],
            no_new_800_CNY_authorization=True,
            cost_and_request_caps_never_reset=True,
        ),
        maximum_generation_requests=256000,
        maximum_generation_requests_may_exceed_remaining_global_request_budget=True,
        global_original_caps_take_precedence=True,
        all_slots_completion_guaranteed=False,
        no_prior_answers_or_author_programs_visible_to_Probe=True,
        no_failure_task_only_topups=True,
        no_old_new_success_splicing=True,
        reference_and_native_scoring_only_after_all_new_generation_sealed=True,
        review=dict(
            design="two single-slot review chains then within-task semantic alignment",
            model="deepseek-flash",
            source_gate=history["review_gate_sha256"],
            technical_admission=history["review_gate"]["admitted"],
            new_review_registration_after_new_generation_seal=True,
        ),
        registration_status="REGISTERED_NOT_STARTED",
        execution_admitted=False,
        blocking_reason="separate_launch_admission_required"
        if history["review_gate"]["admitted"]
        else "decomposed_review_interface_not_admitted",
        new_model_calls=0,
        training_started=False,
        GPU_reservation=False,
        scale_guidance_is_not_a_claim_of_uniform_reference_scaling=True,
        independent_stock_not_a_VTDO_improvement_claim=True,
    )
    return bound(body)


def checked_plan(output):
    plan = read_json(Path(output) / "registration/protocol.json")
    require(
        plan["id"] == digest({k: v for k, v in plan.items() if k != "id"}),
        "new batch registration changed",
    )
    require(plan["runtime_binding"] == runtime_binding(), "new batch source binding changed")
    return plan


def register(output=OUTPUT, review_cohort=REVIEW_COHORT):
    output = Path(output)
    if (output / "registration/protocol.json").exists():
        return checked_plan(output)
    require(not output.exists(), "partial registration cannot be silently overwritten")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in Path(__file__).parent.rglob("*.py"):
        require(
            path.read_bytes()
            == subprocess.check_output(
                ["git", "show", head + ":" + str(path.relative_to(ROOT))], cwd=ROOT
            ),
            "commit frozen new-batch design before registration",
        )
    history = historical_prefix(review_cohort)
    plan = build_plan(head, history)
    publish(output / "historical_audit", history)
    publish(output / "registration", plan, "protocol.json")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--review-cohort", type=Path, default=REVIEW_COHORT)
    args = parser.parse_args(argv)
    plan = (
        register(args.output, args.review_cohort)
        if args.action == "register"
        else checked_plan(args.output)
    )
    print(
        {
            k: plan[k]
            for k in (
                "id",
                "registration_status",
                "task_denominator",
                "slot_denominator",
                "capacity_histogram",
                "execution_admitted",
                "blocking_reason",
                "new_model_calls",
            )
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
