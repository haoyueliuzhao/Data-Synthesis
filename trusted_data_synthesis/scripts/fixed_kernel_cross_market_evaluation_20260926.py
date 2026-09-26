"""Independent PDF evaluation bridge with durable finite budgets and global seal.

No registration or model execution happens on import. The controller must first
freeze an admitted 180-task panel, the nine step240 points and physical budgets.
Existing decoder/receipt/session inventory functions are reused with an explicit
PDF runtime binding. SEC source/scoring globals are never mutated.
"""

from __future__ import annotations

import copy
import fcntl
import multiprocessing
import re
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_B_common_20260922 as legacy
import fixed_kernel_cross_market_runtime_20260926 as views
import fixed_kernel_direction_calibration_evaluation_20260926 as prior

p = prior.p
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_cross_market_evaluation_20260926.py"
PROTOCOL_KIND = "cross_market_evaluation_protocol"
_SCORING = None


def _clone(function, changes):
    return views.prior.isolation.clone_function(function, {**function.__globals__, **changes})


def adapted_old():
    """Isolated namespace; old frozen module bindings remain untouched."""
    feedback = SimpleNamespace(**vars(legacy.old.feedback))
    feedback.generate_jobs = _clone(feedback.generate_jobs, {"views": views})
    feedback.score_one = score_one
    return SimpleNamespace(**{**vars(legacy.old), "views": views, "feedback": feedback})


class Context:
    def __init__(self, raw):
        self.RAW, self.p, self.old = Path(raw).resolve(), p, adapted_old()

    def read_protocol(self, root):
        plan = p.checked(p.read_json(self.RAW / "protocol.json"), PROTOCOL_KIND)
        p.require(plan["frozen"] is True, "cross_market_eval.frozen_plan")
        p.require(
            plan["materials"]["runtime_binding"] == views.binding(),
            "cross_market_eval.frozen_pdf_runtime",
        )
        for name, digest in plan["scientific_sources"].items():
            p.require(p.sha(Path(root) / name) == digest, "cross_market_eval.frozen_source:" + name)
        return plan

    def write(self, path, value, immutable=True):
        path = Path(path)
        p.require(
            path.is_absolute()
            and ".." not in path.parts
            and path.resolve().is_relative_to(self.RAW),
            "cross_market_eval.confined_write",
        )
        legacy.durable.write(path, value, immutable=immutable)
        return value

    @contextmanager
    def locked(self, path, blocking=True):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            try:
                yield stream
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def _budget_state(self):
        path = self.RAW / "budget/state.json"
        return p.read_json(path) if path.exists() else dict(counts={}, committed_generation={})

    def reserve(self, kind, job_key, attempt, unit):
        for component in (kind, job_key, attempt, unit):
            p.require(
                bool(re.fullmatch(r"[A-Za-z0-9_.-]+", str(component)))
                and str(component) not in {".", ".."},
                "cross_market_eval.safe_ledger_component",
            )
        plan = p.checked(p.read_json(self.RAW / "protocol.json"), PROTOCOL_KIND)
        marker = (
            self.RAW / "budget/intents" / kind / str(job_key) / str(attempt) / (str(unit) + ".json")
        )
        with self.locked(self.RAW / "budget.lock"):
            p.require(not marker.exists(), "cross_market_eval.no_same_attempt_retry")
            state = self._budget_state()
            current = state["counts"].get(kind, 0)
            p.require(
                current < plan["physical_budget"][kind + "_cap"],
                "cross_market_eval.physical_budget_exhausted:" + kind,
            )
            if kind == "generate_call":
                credited = sum(row["calls"] for row in state["committed_generation"].values())
                p.require(
                    current - credited < plan["physical_budget"]["incomplete_generate_call_cap"],
                    "cross_market_eval.incomplete_call_budget_exhausted",
                )
            state["counts"][kind] = current + 1
            state["updated_at"] = p.now()
            self.write(self.RAW / "budget/state.json", state, immutable=False)
            self.write(
                marker,
                dict(
                    protocol_id=plan["id"],
                    kind=kind,
                    job_key=job_key,
                    attempt=attempt,
                    unit=unit,
                    reservation_number=current + 1,
                    at=p.now(),
                ),
            )

    def generation_committed(self, point_id, index, record):
        p.checked(record, "anchored_generated_trajectory")
        repeat = record["job"]["repeat"]
        p.require(
            record["point_id"] == point_id
            and record["job"]["index"] == index
            and repeat in {0, 1, 2},
            "cross_market_eval.committed_identity",
        )
        mode = "greedy" if repeat == 0 else "stochastic"
        key = f"{point_id}:{mode}:{index}"
        with self.locked(self.RAW / "budget.lock"):
            state = self._budget_state()
            value = dict(record_id=record["id"], calls=record["actual_generate_calls"])
            p.require(
                state["committed_generation"].get(key, value) == value,
                "cross_market_eval.one_commit_per_point_mode_index",
            )
            state["committed_generation"][key] = value
            p.require(
                sum(row["calls"] for row in state["committed_generation"].values())
                <= state["counts"].get("generate_call", 0),
                "cross_market_eval.calls_precharged",
            )
            self.write(self.RAW / "budget/state.json", state, immutable=False)

    @staticmethod
    def capacity_boundary(phase, required):
        # A controller retry occurs only at a committed boundary, never per-token.
        legacy.torch.cuda.empty_cache()
        free, _ = legacy.torch.cuda.mem_get_info()
        capacity = (free + legacy.torch.cuda.memory_reserved()) / 2**20
        if capacity < required:
            raise legacy.CapacityWait(f"{phase}: {capacity:.0f} MiB available < {required} MiB")


def run_generation(c, root, job, attempt, required=49152):
    # Pure generation cannot read private assets: the prior wrapper only opens
    # public admission/view references and bound model metadata.
    return prior.run_generation(c, root, job, attempt, required=required)


def initialize_scoring(raw, private, source_manifest_id, point_id, stochastic):
    global _SCORING
    _SCORING = (
        Path(raw),
        private,
        source_manifest_id,
        point_id,
        stochastic,
        views.build_runtime(),
        {},
    )


def score_one(item):
    p.require(_SCORING is not None, "cross_market_eval.scoring_initialized_after_seal")
    raw, private, manifest_id, point_id, stochastic, runtime, fixtures = _SCORING
    row = item["job"]["task"]
    if row["task_id"] not in fixtures:
        view, _identity = legacy.old.feedback.given.load_view(raw, row, manifest_id)
        public = legacy.old.feedback.json.loads(view["public_messages"][0]["content"])
        bundle = copy.deepcopy(private["bundles"][row["task_id"]])
        p.require(bundle["public"] == public, "cross_market_eval.exact_private_public_join")
        fixtures[row["task_id"]] = bundle, views.SourceViewSources(public)
    bundle, sources = fixtures[row["task_id"]]
    session = legacy.old.feedback.read_session(raw, item)
    legacy.old.feedback.validate_receipts(session, item, point_id, stochastic)
    result = runtime.assess_session(session, bundle, private["native_bindings"], sources)
    return dict(
        index=item["job"]["index"],
        task_id=row["task_id"],
        repeat=item["job"]["repeat"],
        group=row["group"],
        session_id=session["id"],
        assessment=result,
        Q=int(result["financial_valid"]),
    )


def _score_missing(c, job, attempt, directory, frozen, missing, private, seal, records):
    workers = min(12, len(missing))
    iterator, pending = iter(missing), {}
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=initialize_scoring,
        initargs=(
            str(c.RAW),
            private,
            frozen["source_manifest_id"],
            frozen["point_id"],
            frozen["stochastic"],
        ),
    ) as executor:

        def fill():
            while len(pending) < workers:
                item = next(iterator, None)
                if item is None:
                    return
                c.reserve("score_case", job["key"], attempt, item["job"]["index"])
                pending[executor.submit(score_one, item)] = item

        try:
            fill()
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda value: pending[value]["job"]["index"]):
                    item = pending.pop(future)
                    value = future.result()  # No exception is converted into Q=0.
                    prior.legacy_scoring._validate_score(value, item, assessment=True)
                    row = p.record(
                        "direction_calibration_scored_case",
                        **{key: value[key] for key in prior.SCORE_FIELDS},
                        assessment=value["assessment"],
                        generation_manifest_id=frozen["id"],
                        generation_seal_id=seal["id"],
                        point_id=frozen["point_id"],
                        source_manifest_id=frozen["source_manifest_id"],
                        condition=job["condition"],
                        phase=job["phase"],
                        seed=job["seed"],
                    )
                    index = value["index"]
                    c.write(directory / "score_rows" / f"{index:04d}.json", row)
                    records[index] = row
                    c.write(directory / "assessments" / f"{index:04d}.json", value["assessment"])
                fill()
        except BaseException:
            for future in pending:
                future.cancel()
            raise


def run_scoring(c, root, job, attempt):
    prior._job(job, attempt)
    plan = c.read_protocol(Path(root).resolve())
    manifest = prior.public_manifest(plan)
    directory = prior._helpers(c)._inside_raw(job["directory"], directory=True)
    with prior.legacy_scoring._cohort_lock(directory):
        frozen = prior._sealed_cohort(c, plan, job, directory, manifest)
        seal = prior.require_generation_seal(c, plan, manifest, job["seal_path"])
        p.require(
            any(
                row["seed"] == job["seed"]
                and row["condition"] == job["condition"]
                and row["phase"] == job["phase"]
                and row["point_id"] == job["point_id"]
                and Path(row["generation_manifest_path"]).parent == directory
                for row in seal["cohorts"]
            ),
            "cross_market_eval.scoring_own_sealed_cohort",
        )
        report_path = directory / "scoring_report.json"
        if report_path.exists():
            report = p.checked(p.read_json(report_path), "cross_market_independent_scoring")
            p.require(
                report["protocol_id"] == plan["id"]
                and report["generation_manifest_id"] == frozen["id"]
                and report["generation_seal_id"] == seal["id"]
                and report["runtime_binding_id"] == views.binding()["id"]
                and report["complete"] is True
                and report["denominator"] == len(report["scores"]) == len(frozen["trajectories"])
                and report["qualified"] == sum(row["Q"] for row in report["scores"]),
                "cross_market_eval.reused_report_binding",
            )
            for value, item in zip(report["scores"], frozen["trajectories"], strict=True):
                prior.legacy_scoring._validate_score(value, item, assessment=False)
            return report
        records = prior._score_inventory(directory, frozen, job, seal)
        missing = [item for item in frozen["trajectories"] if item["job"]["index"] not in records]
        private = prior._private_assets(plan, manifest, seal) if missing else None
        for index, value in records.items():
            c.write(directory / "assessments" / f"{index:04d}.json", value["assessment"])
        if missing:
            _score_missing(c, job, attempt, directory, frozen, missing, private, seal, records)
        values = [records[item["job"]["index"]] for item in frozen["trajectories"]]
        report = p.record(
            "cross_market_independent_scoring",
            protocol_id=plan["id"],
            generation_manifest_id=frozen["id"],
            generation_seal_id=seal["id"],
            point_id=frozen["point_id"],
            source_manifest_id=manifest["id"],
            runtime_binding_id=views.binding()["id"],
            complete=True,
            denominator=len(values),
            scores=[{key: row[key] for key in prior.SCORE_FIELDS} for row in values],
            qualified=sum(row["Q"] for row in values),
            condition=job["condition"],
            phase=job["phase"],
            seed=job["seed"],
            source_currency_adapter_changed=True,
            financial_support_principle_unchanged=True,
            scoring_after_all_generation_complete=True,
            private_references_never_sent_to_generator=True,
            calibration_tasks_opened=180,
            confirm_tasks_opened=0,
            finished_at=p.now(),
        )
        c.write(report_path, report)
        return report
