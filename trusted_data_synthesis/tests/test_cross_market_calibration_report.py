"""Synthetic-only sealed report/finite watcher tests; no real Q, model or git."""

import copy
from types import SimpleNamespace

import pytest
import run_cross_market_calibration_report_20260927 as m
from test_cross_market_statistics import fixture as statistical_fixture


def remake(value, kind, **updates):
    body = {k: v for k, v in value.items() if k not in {"id", "schema_version"}}
    return m.p.record(kind, **body | updates)


def sealed_fixture():
    tasks, _, issuer = statistical_fixture(60)
    plan = dict(id="evaluation:synthetic", materials=dict(runtime_binding=dict(id="runtime")))
    manifest = dict(id="manifest:synthetic", tasks=tasks)
    cohorts, reports, generations = [], [], {}
    for arm in m.prior.ARMS:
        for seed in m.prior.SEEDS:
            for mode in m.prior.MODES:
                point = f"point:{arm}:{seed}"
                items, scores = [], []
                for task in tasks:
                    for repeat in (1, 2) if mode == "stochastic" else (0,):
                        index = len(items)
                        session = f"session:{arm}:{seed}:{mode}:{index}"
                        items.append(
                            dict(
                                job=dict(
                                    index=index, task=task, repeat=repeat, seed=900000 + index
                                ),
                                session_id=session,
                            )
                        )
                        scores.append(
                            dict(
                                index=index,
                                task_id=task["task_id"],
                                repeat=repeat,
                                group=task["group"],
                                session_id=session,
                                Q=int(arm == "positive"),
                            )
                        )
                frozen = m.p.record(
                    "anchored_generation_manifest",
                    point_id=point,
                    source_manifest_id=manifest["id"],
                    trajectories=items,
                )
                generations[arm, seed, mode] = frozen
                cohorts.append(
                    dict(
                        key=f"{arm}_{seed}_{mode}",
                        condition=arm,
                        seed=seed,
                        phase=mode,
                        point_id=point,
                    )
                )
                reports.append(
                    dict(
                        protocol_id=plan["id"],
                        generation_manifest_id=frozen["id"],
                        point_id=point,
                        source_manifest_id=manifest["id"],
                        runtime_binding_id="runtime",
                        complete=True,
                        denominator=len(scores),
                        scores=scores,
                        qualified=sum(row["Q"] for row in scores),
                        condition=arm,
                        phase=mode,
                        seed=seed,
                        scoring_after_all_generation_complete=True,
                        private_references_never_sent_to_generator=True,
                        financial_support_principle_unchanged=True,
                        calibration_tasks_opened=180,
                        confirm_tasks_opened=0,
                    )
                )
    seal = m.p.record(
        "calibration_generation_seal",
        protocol_id=plan["id"],
        source_manifest_id=manifest["id"],
        complete=True,
        all_generation_workers_exited=True,
        total_trajectories=4860,
        cohorts=cohorts,
    )
    reports = [
        m.p.record("cross_market_independent_scoring", **row, generation_seal_id=seal["id"])
        for row in reports
    ]
    return plan, manifest, seal, reports, generations, issuer


def test_all4860_join_uses_training_seed_not_generation_sampling_seed():
    plan, manifest, seal, reports, generations, issuer = sealed_fixture()
    outcomes = m.collect_outcomes(plan, manifest, seal, reports, generations)
    assert len(outcomes) == 4860
    assert {row["seed"] for row in outcomes} == {11, 29, 47}
    assert sum(row["decoding"] == "stochastic" for row in outcomes) == 3240
    m.statistics.validate(
        manifest["tasks"],
        outcomes,
        dict.fromkeys(m.statistics.GROUPS, 60),
        m.statistics.admission_mapping(issuer),
    )


@pytest.mark.parametrize(
    "change",
    [
        dict(point_id="wrong"),
        dict(generation_seal_id="wrong"),
        dict(source_manifest_id="wrong"),
        dict(runtime_binding_id="wrong"),
        dict(seed=12),
        dict(condition="delayed_c"),
        dict(phase="confirm"),
        dict(complete=False),
        dict(scoring_after_all_generation_complete=False),
        dict(confirm_tasks_opened=720),
    ],
)
def test_mislabeled_cohort_or_unsealed_report_rejected(change):
    plan, manifest, seal, reports, generations, _ = sealed_fixture()
    reports[0] = remake(reports[0], "cross_market_independent_scoring", **change)
    with pytest.raises(ValueError):
        m.collect_outcomes(plan, manifest, seal, reports, generations)


@pytest.mark.parametrize(
    "field,value",
    [("session_id", "wrong"), ("repeat", 0), ("task_id", "unknown"), ("Q", 0.5), ("index", 999)],
)
def test_bad_single_score_never_becomes_zero_or_another_pair(field, value):
    plan, manifest, seal, reports, generations, _ = sealed_fixture()
    scores = copy.deepcopy(reports[0]["scores"])
    scores[0][field] = value
    reports[0] = remake(
        reports[0],
        "cross_market_independent_scoring",
        scores=scores,
        qualified=sum(row["Q"] for row in scores),
    )
    with pytest.raises(ValueError):
        m.collect_outcomes(plan, manifest, seal, reports, generations)


def test_missing_or_duplicate_cohort_rejected():
    plan, manifest, seal, reports, generations, _ = sealed_fixture()
    with pytest.raises(ValueError, match="eighteen"):
        m.collect_outcomes(plan, manifest, seal, reports[:-1], generations)
    reports[-1] = reports[0]
    with pytest.raises(ValueError, match="one_report"):
        m.collect_outcomes(plan, manifest, seal, reports, generations)


def test_incomplete_seal_cannot_open_outcomes():
    plan, manifest, seal, reports, generations, _ = sealed_fixture()
    seal = remake(seal, "calibration_generation_seal", all_generation_workers_exited=False)
    with pytest.raises(ValueError, match="complete_generation_seal"):
        m.collect_outcomes(plan, manifest, seal, reports, generations)


def test_no_scores_read_before_complete_generation_seal(tmp_path, monkeypatch):
    evaluation = tmp_path / "evaluation"
    evaluation.mkdir()
    plan = dict(
        evaluation_root=str(evaluation), evaluation_protocol={"id": "e"}, source_manifest_id="m"
    )
    seal_path = evaluation / "generation_seal.json"
    m.p.write_once(seal_path, m.p.record("calibration_generation_seal", marker="synthetic"))
    complete = m.p.record(
        "cross_market_evaluation_completed",
        complete=True,
        protocol_id="e",
        source_manifest_id="m",
        scored_sessions=4860,
        scoring_reports=[{"path": "private-score"}] * 18,
        generation_seal=m.reference(seal_path),
    )
    m.p.write_once(evaluation / "complete.json", complete)
    monkeypatch.setattr(
        m.controller.evaluation,
        "Context",
        lambda raw: SimpleNamespace(read_protocol=lambda root: {"id": "e"}),
    )
    monkeypatch.setattr(m.prior, "public_manifest", lambda plan: {"id": "m"})
    opened = []
    monkeypatch.setattr(m.prior, "_reference", lambda value: opened.append(value))

    def not_sealed(*args):
        raise ValueError("no_complete4860_seal")

    monkeypatch.setattr(m.prior, "require_generation_seal", not_sealed)
    with pytest.raises(ValueError, match="no_complete4860_seal"):
        m.load_sealed_inputs(tmp_path, plan)
    assert opened == []


@pytest.fixture
def execution(tmp_path, monkeypatch):
    output = tmp_path / "statistics"
    output.mkdir()
    monkeypatch.setattr(m, "RAW", output)
    plan = dict(id="report-plan", maximum_analysis_attempts=2)
    monkeypatch.setattr(m, "protocol", lambda *args: plan)
    inputs = dict(
        evaluation_completion={"id": "completed-evaluation"}, generation_seal={"id": "seal"}
    )
    monkeypatch.setattr(m, "load_sealed_inputs", lambda *args: ([], [], {}, inputs))
    monkeypatch.setattr(m, "render_report", lambda result: "# Synthetic report\n")
    calls = []

    def analyze(*args):
        calls.append(args)
        return dict(status="COMPLETE")

    monkeypatch.setattr(m.statistics, "analyze", analyze)
    return tmp_path, output, calls


def test_completed_analysis_is_idempotent_and_does_not_reopen_Q(execution, monkeypatch):
    root, output, calls = execution
    completed = m.run(root, output)

    def forbidden(*args):
        raise AssertionError("completed run must not reopen outcomes")

    monkeypatch.setattr(m, "load_sealed_inputs", forbidden)
    assert m.run(root, output) == completed
    assert len(calls) == 1
    assert m.read(output / "analysis_budget.json")["attempts"] == 1


def test_only_one_finite_identical_resource_retry(execution, monkeypatch):
    root, output, calls = execution

    def interrupted(*args):
        raise MemoryError("synthetic resource interruption")

    monkeypatch.setattr(m.statistics, "analyze", interrupted)
    for _ in range(2):
        with pytest.raises(MemoryError):
            m.run(root, output)
    with pytest.raises(ValueError, match="finite_analysis_attempt_cap"):
        m.run(root, output)
    assert m.read(output / "analysis_budget.json")["attempts"] == 2
    assert calls == []


def test_numeric_failure_not_retried(execution, monkeypatch):
    root, output, _ = execution

    def broken(*args):
        raise ValueError("synthetic invalid analysis")

    monkeypatch.setattr(m.statistics, "analyze", broken)
    with pytest.raises(ValueError, match="synthetic invalid"):
        m.run(root, output)
    with pytest.raises(ValueError, match="no_unknown_or_numeric"):
        m.run(root, output)
    assert m.read(output / "analysis_budget.json")["attempts"] == 1


def test_publication_retry_only_stages_report_paths_and_never_reanalyzes(execution, monkeypatch):
    root, output, calls = execution
    m.run(root, output)
    invoked, pushes = [], []

    def execute(command, **kwargs):
        invoked.append(command)
        if "push" in command:
            pushes.append(command)
            if len(pushes) == 1:
                raise OSError("synthetic push failure")
        return SimpleNamespace(returncode=1 if "diff" in command else 0)

    monkeypatch.setattr(m.subprocess, "run", execute)
    monkeypatch.setattr(m.subprocess, "check_output", lambda *args, **kwargs: "synthetic-head\n")
    assert m.publish(root, output) is False
    assert (root / m.PUBLIC).exists()
    pending = m.read(output / "publication.json")
    monkeypatch.setattr(m.time, "time", lambda: pending["not_before"] + 1)
    assert m.publish(root, output) is True
    assert m.publish(root, output) is True
    assert len(calls) == 1
    assert len(pushes) == 2
    staged = [command for command in invoked if "add" in command]
    assert all(command[-2:] == [m.PUBLIC, m.DOCUMENT] for command in staged)


def test_report_preserves_separate_comparisons_and_not_original_confirmation():
    tasks, outcomes, issuer = statistical_fixture(1)
    analysis = m.statistics.analyze_synthetic_for_test(
        tasks,
        outcomes,
        issuer,
        sizes={g: 1 for g in m.statistics.GROUPS},
        replicates=11,
        max_draws=100,
    )
    result = dict(
        analysis=analysis,
        inputs=dict(evaluation_completion={"id": "e"}, generation_seal={"id": "s"}),
    )
    rendered = m.render_report(result)
    assert all(name in rendered for name in analysis["comparisons"])
    assert all(group in rendered for group in m.statistics.GROUPS)
    assert "原美股B确认的正向训练价值仍未确认" in rendered
    assert "full_400_step_independent_confirmation" in rendered
    assert "未读图像" in rendered


def test_watch_waits_for_protocol_without_opening_scores_or_analyzing(tmp_path, monkeypatch):
    output, evaluation = tmp_path / "statistics", tmp_path / "evaluation"
    monkeypatch.setattr(m, "RAW", output)
    monkeypatch.setattr(m.controller, "RAW", evaluation)
    monkeypatch.setattr(m, "committed_sources", lambda root: ("head", {}))
    monkeypatch.setattr(m.controller, "process_identity", lambda pid: "birth")

    def unexpected(*args):
        raise AssertionError("not before evaluation protocol")

    monkeypatch.setattr(m, "register", unexpected)
    monkeypatch.setattr(m.statistics, "analyze", unexpected)

    def stop(seconds):
        assert seconds == 30
        raise KeyboardInterrupt

    monkeypatch.setattr(m.time, "sleep", stop)
    with pytest.raises(KeyboardInterrupt):
        m.watch(tmp_path, output)
    assert m.read(output / "status.json")["status"] == "WAITING_EVALUATION_PROTOCOL"


def test_active_worker_birth_blocks_analysis(tmp_path, monkeypatch):
    path = tmp_path / "control/attempts/job/1/started.json"
    m.p.write_once(path, dict(pid=456, process_identity="same-birth"))
    monkeypatch.setattr(m.controller, "process_identity", lambda pid: "same-birth")
    with pytest.raises(ValueError, match="workers_exited"):
        m.require_workers_exited(tmp_path)
    monkeypatch.setattr(m.controller, "process_identity", lambda pid: "reused-new-birth")
    m.require_workers_exited(tmp_path)


def test_worker_started_identity_supersedes_early_unknown_launch(tmp_path, monkeypatch):
    directory = tmp_path / "control/attempts/job/1"
    m.p.write_once(directory / "started.json", dict(pid=456, process_identity="known"))
    m.p.write_once(directory / "launched.json", dict(pid=456, process_identity=None))
    monkeypatch.setattr(m.controller, "process_identity", lambda pid: None)
    m.require_workers_exited(tmp_path)


def test_unknown_birth_is_safe_only_if_pid_no_longer_running(tmp_path, monkeypatch):
    directory = tmp_path / "control/attempts/job/1"
    m.p.write_once(directory / "launched.json", dict(pid=456, process_identity=None))
    monkeypatch.setattr(m.controller, "process_identity", lambda pid: "some-live-birth")
    with pytest.raises(ValueError, match="unknown_live_worker"):
        m.require_workers_exited(tmp_path)
    monkeypatch.setattr(m.controller, "process_identity", lambda pid: None)
    m.require_workers_exited(tmp_path)


def test_publication_attempt_reserved_before_any_git_operation(execution, monkeypatch):
    root, output, calls = execution
    m.run(root, output)

    def killed(command, **kwargs):
        state = m.read(output / "publication.json")
        assert state["attempt"] == 1
        assert state["status"] == "PUBLICATION_IN_PROGRESS_NO_REANALYSIS"
        raise KeyboardInterrupt

    monkeypatch.setattr(m.subprocess, "run", killed)
    with pytest.raises(KeyboardInterrupt):
        m.publish(root, output)
    assert m.read(output / "publication.json")["attempt"] == 1
    assert len(calls) == 1


def test_register_binds_public_inputs_without_touching_private_scores(tmp_path, monkeypatch):
    output, evaluation = tmp_path / "statistics", tmp_path / "evaluation"
    monkeypatch.setattr(m, "RAW", output)
    monkeypatch.setattr(m.controller, "RAW", evaluation)
    monkeypatch.setattr(m, "committed_sources", lambda root: ("committed-test", {}))
    tasks, _, issuer = statistical_fixture(60)
    issuer_path = tmp_path / "issuer.json"
    m.p.write_once(issuer_path, issuer)
    manifest = m.p.record(
        "source_view_manifest_v2",
        split="calibration",
        tasks=[{**task, "path": str(tmp_path / (task["task_id"] + ".json"))} for task in tasks],
    )
    manifest_path = tmp_path / "manifest.json"
    m.p.write_once(manifest_path, manifest)
    compilation = m.p.record(
        "synthetic_panel_compilation",
        full_original_PDF_visual_exhaustion_claimed=False,
        source_text_table_review_bundle_id="synthetic-text-reviews",
        source_text_table_reviews={"path": "/synthetic/reviews.json", "sha256": "a" * 64},
        source_text_table_review_scope="saved_text",
    )
    m.p.write_once(tmp_path / "panel/protocol.json", compilation)
    admission = m.p.record(
        "calibration_panel_admission",
        passed=True,
        source_manifest_id=manifest["id"],
        issuer_admission=m.reference(issuer_path),
        compilation_protocol_id=compilation["id"],
    )
    admission_path = tmp_path / "panel/public/admission.json"
    m.p.write_once(admission_path, admission)
    plan = m.p.record(
        m.controller.evaluation.PROTOCOL_KIND,
        panel=dict(
            manifest=m.reference(manifest_path),
            admission=m.reference(admission_path),
            private_assets={"path": "/forbidden/private.json"},
        ),
        scientific_sources={},
    )
    m.p.write_once(evaluation / "protocol.json", plan)
    monkeypatch.setattr(
        m.controller.evaluation,
        "Context",
        lambda raw: SimpleNamespace(read_protocol=lambda root: plan),
    )
    real_reference = m.prior._reference
    opened = []

    def public_only(reference):
        opened.append(reference["path"])
        assert reference["path"] != "/forbidden/private.json"
        return real_reference(reference)

    monkeypatch.setattr(m.prior, "_reference", public_only)
    result = m.register(tmp_path, evaluation, output)
    assert result["no_outcomes_opened_during_registration"] is True
    assert result["outcome_count"] == 4860
    assert result["bootstrap"] == dict(seed=20260926, valid_replicates=20000, maximum_draws=200000)
    assert len(opened) >= 3
    assert not (output / "analysis_budget.json").exists()
