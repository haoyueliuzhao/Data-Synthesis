"""Metadata-only CPU fault injection; no Student tensors, model, GPU or API load."""

import copy
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research import v8_training_driver as training


def fake_driver(tmp_path, monkeypatch, *, fail_phase=None, failure=None):
    events = []
    driver = training.TrainingDriver.__new__(training.TrainingDriver)
    driver.root, driver.seed, driver.arm = tmp_path / "training", 11, "Full"
    driver.step_index = driver.shared_step = 298
    driver.outer_steps, driver.final_step, driver.sharing_split_step = (
        (298, 596, 894, 1192),
        1490,
        894,
    )
    driver.tainted, driver.outer_done = False, []
    driver.pool = SimpleNamespace(
        cache_id="CPU-metadata-only-pool",
        production_verified=False,
        _manifest=SimpleNamespace(registration=SimpleNamespace(mu={"task": "1"})),
    )
    driver.schedule = {"schedule_sha256": "CPU-schedule"}
    driver.parameters, driver.device, driver.tokenizer = {}, "cpu", None
    driver.model = SimpleNamespace(named_buffers=lambda: [])
    driver.optimizer = SimpleNamespace(state_dict=lambda: {"CPU_metadata_only": True})
    driver.base_digest = "CPU-base"
    driver.pi = {"task": {"state": "1"}}
    driver.prior = copy.deepcopy(driver.pi)
    driver._payload = lambda: {"CPU_metadata_only": True}
    driver.step = lambda: pytest.fail("failed first outer must not depart step298")

    def stage(name, value):
        events.append(name)
        if fail_phase == name:
            raise failure
        return value

    monkeypatch.setattr(
        training, "class_gradients", lambda *a, **kw: stage("full_class_gradients", {})
    )
    monkeypatch.setattr(
        training,
        "prepare_virtual_point",
        lambda *a, **kw: stage("virtual_Adam", {"theta_bar": {}, "G": {}}),
    )
    monkeypatch.setattr(training, "parameter_digest", lambda value: "CPU-empty-vector-digest")
    monkeypatch.setattr(training, "_rng", lambda: {"CPU_rng_placeholder": True})
    monkeypatch.setattr(training, "installed_point", lambda *a: nullcontext({}))

    def replay(*args, event_sink=None, **kwargs):
        if event_sink is not None:
            event_sink(
                dict(
                    event="feedback_response_backward",
                    trajectory=0,
                    call_id="CPU-completed-response",
                    responses_replayed=1,
                )
            )
        return stage("logP_replay", ({}, {"CPU_metadata_only": True}))

    monkeypatch.setattr(training, "feedback_gradient", replay)
    monkeypatch.setattr(
        training,
        "update_distribution",
        lambda *a, **kw: stage(
            "optimizer_pullback_Contribution_and_pi",
            {"distribution": {"pi_next": copy.deepcopy(driver.pi)}, "a": {}, "C": {}},
        ),
    )
    cohort = SimpleNamespace(
        denominator=700, seal_sha256="CPU-cohort", model_dump=lambda **kw: {"denominator": 700}
    )

    class Collector:
        def collect(self, model, tokenizer, theta, *, point_id, event_sink=None):
            phase = (
                fail_phase
                if fail_phase
                in {"feedback_generation", "feedback_cohort_validation", "native_scoring"}
                else "feedback_generation"
            )
            event_sink(dict(phase=phase, feedback_root=str(tmp_path / "feedback")))
            return stage(phase, (cohort, [0] * 700))

    monkeypatch.setattr(training, "LocalFeedbackCollector", Collector)
    driver.collector = Collector()

    def commit(phase, evidence, **kwargs):
        stage("outer_commit", None)
        path = driver.root / f"step{driver.step_index:04d}_{phase}"
        path.mkdir(parents=True)
        (path / "record.json").write_text(json.dumps({"CPU_metadata_only": True}))
        return path

    driver.commit = commit
    return driver, events


@pytest.mark.parametrize(
    "phase,error,kind",
    [
        ("full_class_gradients", MemoryError("CPU injected allocation failure"), "resource_OOM"),
        ("virtual_Adam", ValueError("nonfinite population gradient"), "nonfinite_numeric"),
        (
            "feedback_generation",
            ValueError("missing feedback receipt"),
            "missing_or_incomplete_feedback",
        ),
        (
            "feedback_cohort_validation",
            ValueError("incomplete registered cohort"),
            "missing_or_incomplete_feedback",
        ),
        (
            "native_scoring",
            ValueError("infrastructure/reference unknown cannot become zero reward"),
            "scoring_infrastructure_failure",
        ),
        (
            "logP_replay",
            ValueError("replayed probabilities differ from actual sampling receipts"),
            "logP_replay_mismatch",
        ),
        (
            "optimizer_pullback_Contribution_and_pi",
            ValueError("pullback shape contract"),
            "other_engineering_failure",
        ),
        (
            "outer_commit",
            OSError("CPU injected checkpoint IO failure"),
            "other_engineering_failure",
        ),
    ],
)
def test_first_outer_failure_records_true_phase_and_never_runs_step299(
    tmp_path, monkeypatch, phase, error, kind
):
    driver, events = fake_driver(tmp_path, monkeypatch, fail_phase=phase, failure=error)
    with pytest.raises(type(error)) as caught:
        driver.run_until(299)
    assert caught.value is error and driver.tainted and driver.step_index == 298
    saved = json.loads(Path(error.outer_failure_audit["path"]).read_bytes())
    assert saved["last_phase"] == phase and saved["failure_kind"] == kind
    assert saved["step"] == saved["last_committed_training_step"] == 298
    assert saved["arm"] == "Full" and saved["seed"] == 11
    assert saved["stopped_before_next_training_step"]
    assert not saved["failure_counted_as_Q_zero"] and not saved["feedback_resampled"]
    assert not saved["context_or_denominator_changed"] and not saved["automatic_retry"]
    assert not saved["outer_commit_record_exists"]
    assert Path(saved["intent"]["path"]).is_file()
    assert Path(saved["last_phase_record"]["path"]).is_file()
    if phase == "logP_replay":
        assert saved["last_completed_replay_response"]["call_id"] == "CPU-completed-response"
    assert events.count(phase) == 1


def test_success_audit_does_not_repeat_any_calculation_or_create_a_pilot(tmp_path, monkeypatch):
    driver, events = fake_driver(tmp_path, monkeypatch)
    before = copy.deepcopy(driver.pi)
    driver.outer_update()
    assert events == [
        "full_class_gradients",
        "virtual_Adam",
        "feedback_generation",
        "logP_replay",
        "optimizer_pullback_Contribution_and_pi",
        "outer_commit",
    ]
    assert driver.pi == before and driver.outer_done == [298] and not driver.tainted
    complete = json.loads(
        (driver.root / "outer_attempts/step0298/attempt001/complete/record.json").read_bytes()
    )
    assert complete["outer_commit_completed"] and complete["optimizer_steps_in_outer"] == 0
    intent = json.loads(Path(complete["intent"]["path"]).read_bytes())
    assert intent["formal_experiment_not_pilot"] and intent["CPU_control_only"]


def test_classifier_does_not_guess_nonfinite_from_finance_word():
    assert (
        training.outer_failure_kind(ValueError("financial source contract"), "virtual_Adam")
        == "other_engineering_failure"
    )


def test_wrapped_generation_oom_uses_retained_provider_failure_type(tmp_path, monkeypatch):
    error = ValueError("incomplete provider execution retained: CPU-episode")
    driver, _ = fake_driver(tmp_path, monkeypatch, fail_phase="feedback_generation", failure=error)
    path = tmp_path / "feedback/draw0/incomplete/CPU-episode/record.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            dict(
                episode_key="CPU-episode",
                stop_reason="provider_error",
                call_settlements=[dict(evidence=dict(exception_type="OutOfMemoryError"))],
            )
        )
    )
    with pytest.raises(ValueError):
        driver.run_until(299)
    saved = json.loads(Path(error.outer_failure_audit["path"]).read_bytes())
    assert saved["failure_kind"] == "resource_OOM"
    assert saved["retained_incomplete_feedback"][0]["exception_types"] == ["OutOfMemoryError"]
    assert (
        training.outer_failure_kind(
            ValueError("adjoint.saved_sampling_probability_mismatch"), "logP_replay"
        )
        == "logP_replay_mismatch"
    )


def test_unknown_scoring_saves_all700_positions_with_none_before_rejecting(tmp_path, monkeypatch):
    from trusted_synthesis.finance_research import planning, storage, v6_task

    collector = training.LocalFeedbackCollector.__new__(training.LocalFeedbackCollector)
    collector.root, collector.snapshot = tmp_path / "feedback", tmp_path / "snapshot"
    collector.seeds, collector.model_id = (11, 29), "CPU-model-identity"
    collector.manifest, collector.role_plan = {"id": "CPU-snapshot"}, {"id": "CPU-roles"}
    collector.tasks = collector.public = [SimpleNamespace(task_id=f"q{i}") for i in range(350)]
    collector.lineages = [None] * 350
    collector.config = SimpleNamespace(
        model_copy=lambda update: SimpleNamespace(seed=update["seed"])
    )
    monkeypatch.setattr(planning, "task_key", lambda task: task.task_id)
    monkeypatch.setattr(training, "installed_point", lambda *args: nullcontext({}))
    monkeypatch.setattr(
        training,
        "local_model_identity",
        lambda *a, **kw: SimpleNamespace(model_dump=lambda **opts: {"CPU_identity": True}),
    )
    monkeypatch.setattr(training, "LocalTorchProvider", lambda *a, **kw: object())
    monkeypatch.setattr(training, "TaskBundle", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(training, "episode_key", lambda ep: f"{ep.task_id}-seed{ep.config.seed}")
    calls = []

    def prepare(*args, **kwargs):
        root = Path(args[2])
        (root / "generation_seal").mkdir(parents=True)
        (root / "generation_seal/seal.json").write_text("{}")

    async def execute(root, provider):
        calls.append(str(root))

    def episodes(root):
        seed = 11 if Path(root).name == "draw0" else 29
        return (
            None,
            None,
            [
                SimpleNamespace(task_id=f"q{i}", config=SimpleNamespace(seed=seed))
                for i in range(350)
            ],
        )

    def seal(episodes, *, denominator, **kwargs):
        assert len(calls) == 2 and len(episodes) == denominator == 700
        return SimpleNamespace(
            denominator=700,
            seal_sha256="CPU-complete700",
            model_dump=lambda **opts: {"denominator": 700},
        )

    monkeypatch.setattr(storage, "prepare_run", prepare)
    monkeypatch.setattr(storage, "execute_run", execute)
    monkeypatch.setattr(storage, "sealed_episodes", episodes)
    monkeypatch.setattr(storage, "_read_snapshot_rows", lambda *a: [None] * 350)
    monkeypatch.setattr(training, "seal_feedback_cohort", seal)

    def score(bundle, episode):
        unknown = episode.task_id == "q17" and episode.config.seed == 29
        return dict(
            task_id=episode.task_id,
            status="unknown" if unknown else "scored",
            reason="native_scoring_unavailable:RuntimeError" if unknown else None,
            native=dict(execution_accuracy=None if unknown else 1.0),
        )

    monkeypatch.setattr(v6_task, "score_public_reasoning_program", score)
    phases = []
    with pytest.raises(ValueError, match="unknown cannot become zero"):
        collector.collect(object(), object(), {}, point_id="CPU-point", event_sink=phases.append)
    root = collector.root / training.digest("CPU-point")
    diagnostic = json.loads((root / "native_scoring_failure/record.json").read_bytes())
    assert diagnostic["denominator"] == len(diagnostic["positions"]) == 700
    assert diagnostic["not_rewards_admitted"]
    assert diagnostic["unmodified_native_values"][367] is None
    assert diagnostic["unmodified_native_values"].count(None) == 1
    assert diagnostic["positions"][367]["episode_key"] == "q17-seed29"
    assert (
        diagnostic["positions"][367]["score"]["reason"] == "native_scoring_unavailable:RuntimeError"
    )
    assert not diagnostic["missing_or_unknown_values_imputed"]
    assert not diagnostic["feedback_resampled"] and len(calls) == 2
    assert not (root / "native_rewards").exists()
    assert phases[-1]["phase"] == "native_scoring"


def test_v18_binding_is_not_reported_as_old_v8_supervision():
    assert training.material_report_identity("v18_researcher_complete_material_binding.v1") == (
        "v18",
        "v14_state_independent_original_span_union.v1",
    )
