"""CLI acceptance uses only synthetic source data and scripted zero-model turns."""

from __future__ import annotations

import json

import pytest

from trusted_synthesis.finance_research import cli, providers, storage
from trusted_synthesis.finance_research.contracts import ModelIdentity, RunConfig


@pytest.fixture(autouse=True)
def disallow_actual_model_backends(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("this CLI test must not initialize any real API/GPU provider")

    monkeypatch.setattr(providers, "DeepSeekFlashProvider", forbidden)
    monkeypatch.setattr(providers, "LocalTorchProvider", forbidden)
    monkeypatch.setattr(cli, "_local_provider", forbidden)
    monkeypatch.setattr(cli, "_key", forbidden)


def write_raw_finqa(path):
    rows = [
        {
            "id": "CLI_FIXTURE/2020/page_1.pdf-1",
            "filename": "CLI_FIXTURE/2020/page_1.pdf",
            "pre_text": ["This is a synthetic CLI fixture."],
            "post_text": ["Complete footer."],
            "table": [["Year", "Revenue"], ["2020", "8"], ["2019", "2"]],
            "qa": {
                "question": "What is the increase?",
                "exe_ans": 6,
                "program": "subtract(8, 2)",
                "gold_inds": {"table_1": "PRIVATE_CLI_ANCHOR"},
            },
        }
    ]
    path.write_text(json.dumps(rows))
    return rows


def test_catalog_is_readonly_and_does_not_initialize_model_providers(capsys):
    assert cli.main(["catalog"]) == 0
    catalog = json.loads(capsys.readouterr().out)
    assert catalog["finqa"]["role"] == "main_training_and_same_family_test"
    assert catalog["financemath"]["role"] == "external_evaluation_only"
    assert catalog["openenv290"]["role"] == "evaluation_only"


def test_offline_import_and_role_plan_preserve_public_context_and_do_not_start_generation(
    tmp_path, capsys
):
    raw_path, snapshot, roles = tmp_path / "raw.json", tmp_path / "snapshot", tmp_path / "roles"
    raw = write_raw_finqa(raw_path)
    assert (
        cli.main(
            [
                "import",
                "--dataset",
                "finqa",
                "--split",
                "train",
                "--revision",
                "fixture-v1",
                "--input",
                str(raw_path),
                "--output",
                str(snapshot),
            ]
        )
        == 0
    )
    imported = json.loads(capsys.readouterr().out)
    assert imported["counts"] == {"finqa": 1}
    _, tasks, _ = storage.load_public_snapshot(snapshot)
    assert [source.content for source in tasks[0].sources] == [
        *raw[0]["pre_text"],
        raw[0]["table"],
        *raw[0]["post_text"],
    ]
    assert "PRIVATE_CLI_ANCHOR" not in (snapshot / "public.jsonl").read_text()
    assert (
        cli.main(
            [
                "plan",
                "--snapshot",
                str(snapshot),
                "--output",
                str(roles),
                "--sft-tasks",
                "0",
                "--feedback-tasks",
                "0",
                "--calibration-tasks",
                "1",
            ]
        )
        == 0
    )
    planned = json.loads(capsys.readouterr().out)
    assert planned["actual_counts"] == {"calibration": 1}
    assert not list(tmp_path.rglob("episode.json"))
    assert not list(tmp_path.rglob("generation_seal"))


def test_synthetic_preflight_has_zero_actual_model_calls_and_official_native_score(
    tmp_path, capsys
):
    output = tmp_path / "preflight"
    assert cli.main(["preflight", "--output", str(output)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["passed"] and summary["fixture_only"]
    assert summary["real_model_calls"] == 0 and summary["API_calls"] == 0
    assert not summary["native_dataset_or_training_value_claimed"]
    report = storage.read_json(output / "scoring" / "report.json")
    assert report["fixture_only"] and not report["real_model_execution"]
    assert report["results"][0]["native"]["status"] == "scored"
    assert report["results"][0]["native"]["native"] == {
        "execution_accuracy": 1.0,
        "program_accuracy": 1.0,
    }
    assert report["results"][0]["trajectory"]["actual_model_calls"] == 0
    assert report["results"][0]["trajectory"]["provider_attempts"] == 3
    seal = storage.read_json(output / "generation" / "generation_seal" / "seal.json")
    assert seal["complete"] and seal["private_references_read"] is False
    episode = storage.read_json(output / "generation" / seal["episodes"][0]["path"])
    assert episode["final_answer"] == "6"
    assert episode["final_program"] == "subtract(8, 2)"
    assert [event["name"] for event in episode["tool_events"]] == [
        "read_source",
        "calculate",
        "final_answer",
    ]
    assert all(turn["receipt"] is None for turn in episode["turns"])


def test_cli_score_requires_seal_and_does_not_open_private_references(
    tmp_path, capsys, monkeypatch
):
    raw_path, snapshot, roles, run = (
        tmp_path / name for name in ("raw.json", "snapshot", "roles", "run")
    )
    write_raw_finqa(raw_path)
    cli.main(
        [
            "import",
            "--dataset",
            "finqa",
            "--split",
            "train",
            "--revision",
            "fixture-v1",
            "--input",
            str(raw_path),
            "--output",
            str(snapshot),
        ]
    )
    cli.main(
        [
            "plan",
            "--snapshot",
            str(snapshot),
            "--output",
            str(roles),
            "--sft-tasks",
            "0",
            "--feedback-tasks",
            "0",
            "--calibration-tasks",
            "1",
        ]
    )
    capsys.readouterr()
    storage.prepare_run(
        snapshot,
        storage.read_json(roles / "plan.json"),
        run,
        role="calibration",
        config=RunConfig(role="calibration"),
        identity=ModelIdentity(backend="scripted", model_id="cli-unrun-fixture"),
    )
    opened_private = []
    original_read = storage._read_snapshot_rows

    def track_private(path, name, cls, manifest):
        if name == "private.references.jsonl":
            opened_private.append(name)
        return original_read(path, name, cls, manifest)

    monkeypatch.setattr(storage, "_read_snapshot_rows", track_private)
    with pytest.raises((FileNotFoundError, ValueError)):
        cli.main(["score", "--run", str(run), "--output", str(tmp_path / "forbidden-score")])
    assert not opened_private
    assert not (tmp_path / "forbidden-score").exists()


@pytest.mark.parametrize(
    "mixed_argument",
    [
        ["--snapshot", "unused-snapshot"],
        ["--role-plan", "unused-plan.json"],
        ["--role", "test"],
        ["--config", "unused-config.json"],
        ["--limit", "1"],
    ],
)
def test_resume_rejects_new_registration_arguments_before_initializing_a_provider(
    tmp_path,
    capsys,
    mixed_argument,
):
    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "run",
                "--provider",
                "deepseek",
                "--resume",
                "--output",
                str(tmp_path / "run"),
                *mixed_argument,
            ]
        )
    assert error.value.code == 2
    assert "resume uses its frozen registration" in capsys.readouterr().err


def test_new_run_requires_explicit_inputs_before_any_api_key_read_or_request(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["run", "--provider", "deepseek", "--output", str(tmp_path / "run")])
    assert error.value.code == 2
    assert "new run requires" in capsys.readouterr().err
    assert not (tmp_path / "run").exists()
