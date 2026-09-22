"""Synthetic CPU controls for confirmation boundaries, without panel contents."""

import copy
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
confirm = importlib.import_module("fixed_kernel_B_confirm_views_20260922")
p = confirm.p


def rows():
    return [
        dict(
            task_id=f"task_{index:064x}",
            group=group,
            source_cluster=f"cik:{index % 71:010d}",
            surface_version_id=f"surface:{index}",
            public_messages_sha256=p.sha(str(index)),
        )
        for index, group in enumerate(group for group in confirm.GROUPS for _ in range(240))
    ]


def protocol(root, *, frozen=True):
    result = p.record(
        "B_confirm_protocol",
        frozen=frozen,
        candidate="Delayed-C",
        baseline="Static",
        split="confirm",
        confirm_tasks=720,
        tasks_per_group=240,
        seeds=[11, 29, 47],
        models_count=6,
        all_generation_before_private_scoring=True,
        confirm_registry_sha256=p.sha(p.encode(rows())),
        confirm_views=dict(
            protocol_path=str(root / "protocol.json"),
            output_directory=str(root / "new_views"),
            source_root=str(root),
        ),
    )
    p.write_once(root / "protocol.json", result)
    return result


def record_again(record, **fields):
    kind = record["id"].split(":", 1)[0]
    body = {key: value for key, value in record.items() if key not in {"id", "schema_version"}}
    return p.record(kind, **(body | fields))


def public_fixture():
    public = {
        "question": "Synthetic public question",
        "period_contract": {"periods": [{"start": "2020-01-01", "end": "2021-12-31"}]},
        "quantity_contract": {"unit": "USD"},
        "tool_contract": dict.fromkeys(
            ("calculate", "select_max", "compare", "lookup_selected", "Final"), "synthetic"
        ),
    }
    document = {
        "id": "document:synthetic",
        "source_id": "raw:synthetic",
        "native_annual_records": [
            dict(
                source_kind="original_companyfacts_observation",
                raw_sha256="synthetic-sha",
                native_pointer=f"/facts/{index}",
                original_url="https://example.invalid/",
                unit="USD",
                label=concept,
                definition="Synthetic original definition",
                concept=concept,
                record={"end": end, "val": index + 1},
            )
            for index, (concept, end) in enumerate(
                [
                    ("Revenue", "2020-12-31"),
                    ("UnrequestedMetric", "2021-12-31"),
                    ("Revenue", "2025-12-31"),
                ]
            )
        ],
    }
    return public, document


def seal_fixture(root):
    frozen = protocol(root)
    tasks = rows()
    manifest = p.record(
        "source_view_manifest_v2", protocol_id=frozen["id"], split="confirm", tasks=tasks
    )
    models = []
    for condition in confirm.CONDITIONS:
        for seed in confirm.SEEDS:
            key = f"B_{condition}_{seed}"
            point_id = "point:" + key
            generated = p.record(
                "anchored_generation_manifest",
                complete=True,
                stochastic=False,
                point_id=point_id,
                source_manifest_id=manifest["id"],
                tasks=tasks,
                trajectories=[
                    dict(
                        job=dict(index=index, task=row, repeat=0),
                        point_id=point_id,
                        private_assessment_performed=False,
                    )
                    for index, row in enumerate(tasks)
                ],
            )
            path = root / key / "generation_manifest.json"
            p.write_once(path, generated)
            models.append(
                dict(
                    key=key,
                    condition=condition,
                    seed=seed,
                    point_id=point_id,
                    generation_manifest_path=str(path),
                    generation_manifest_sha256=p.sha(path),
                )
            )
    seal = p.record(
        "B_confirm_generation_seal",
        complete=True,
        all_generation_workers_exited=True,
        protocol_id=frozen["id"],
        source_manifest_id=manifest["id"],
        total_trajectories=4320,
        models=models,
    )
    path = root / "seal.json"
    p.write_once(path, seal)
    return frozen, manifest, seal, path


def test_registry_returns_only_fixed_metadata_and_never_opens_task_files(tmp_path):
    expected = rows()
    p.write_once(
        tmp_path / confirm.REGISTRY,
        p.record(
            "execution_freeze",
            evaluation_registry={
                "confirm": expected,
                "dev": [dict(task_id="dev", source_cluster="cik:9999999999")],
            },
        ),
    )
    assert confirm.registry(tmp_path) == expected
    assert all(set(row) == set(confirm.FIELDS) for row in confirm.registry(tmp_path))


@pytest.mark.parametrize("change", ["duplicate", "wrong_group", "bad_cik", "dev_overlap"])
def test_registry_rejects_changed_panel_identity(tmp_path, change):
    tasks = rows()
    dev = []
    if change == "duplicate":
        tasks[1]["task_id"] = tasks[0]["task_id"]
    elif change == "wrong_group":
        tasks[0]["group"] = tasks[-1]["group"]
    elif change == "bad_cik":
        tasks[0]["source_cluster"] = "issuer:1"
    else:
        dev = [dict(task_id="dev", source_cluster=tasks[0]["source_cluster"])]
    p.write_once(
        tmp_path / confirm.REGISTRY,
        p.record(
            "execution_freeze",
            evaluation_registry=dict(confirm=tasks, dev=dev),
        ),
    )
    with pytest.raises(ValueError, match="B_confirm"):
        confirm.registry(tmp_path)


def test_unfrozen_protocol_rejected_before_public_capability(tmp_path, monkeypatch):
    frozen = protocol(tmp_path, frozen=False)
    monkeypatch.setattr(
        confirm.compiler, "modules", lambda _: pytest.fail("opened public capability")
    )
    with pytest.raises(ValueError, match="frozen_unique_candidate"):
        confirm.prepare_views(tmp_path, frozen)
    assert not (tmp_path / "new_views").exists()


def test_changed_code_rejected_before_public_capability(tmp_path, monkeypatch):
    frozen = protocol(tmp_path)
    bound = {name: p.sha("original") for name in confirm.CODE_PATHS}
    frozen = record_again(
        frozen,
        confirm_views={
            **frozen["confirm_views"],
            "code_commit": "committed",
            "code_sources": bound,
        },
    )
    monkeypatch.setattr(confirm.p, "read_json", lambda _: frozen)
    monkeypatch.setattr(confirm.subprocess, "check_output", lambda *args, **kwargs: b"changed")
    monkeypatch.setattr(
        confirm.compiler, "modules", lambda _: pytest.fail("opened public capability")
    )
    with pytest.raises(ValueError, match="code_committed_and_unchanged"):
        confirm.prepare_views(tmp_path, frozen)


def test_original_public_rules_and_absolute_directory_route(tmp_path):
    public, document = public_fixture()
    row = rows()[0]
    identity = dict(
        task_id=row["task_id"],
        family=row["group"],
        surface_version_id=row["surface_version_id"],
        public_messages_sha256=row["public_messages_sha256"],
        parent_manifest_id="original",
    )
    view, expanded = confirm.compile_view(public, document, row, identity, "frozen-rule")
    expected, _ = confirm.compiler.compile_public(public, document, p)
    assert expanded == expected
    assert {source["concept"] for source in expanded["sources"]} == {"Revenue", "UnrequestedMetric"}
    path = tmp_path / "data_disk" / "view.json"
    p.write_once(path, view)
    routed = {
        **row,
        "path": str(path),
        "surface_version_id": view["id"],
        "public_messages_sha256": view["public_messages_sha256"],
    }
    loaded, new_identity = confirm.given.load_view(
        tmp_path / "different_root", routed, "confirm-manifest"
    )
    assert loaded == view
    assert new_identity["parent_manifest_id"] == "confirm-manifest"


def test_complete_global_seal_accepts_all_six_cohorts(tmp_path):
    frozen, manifest, seal, path = seal_fixture(tmp_path)
    assert confirm.require_generation_seal(tmp_path, frozen, manifest, path) == seal


@pytest.mark.parametrize(
    "change", ["missing_model", "still_running", "wrong_count", "duplicate_seed"]
)
def test_global_seal_rejects_partial_or_changed_matrix(tmp_path, change):
    frozen, manifest, seal, _ = seal_fixture(tmp_path)
    if change == "missing_model":
        invalid = record_again(seal, models=seal["models"][:-1])
    elif change == "still_running":
        invalid = record_again(seal, all_generation_workers_exited=False)
    elif change == "wrong_count":
        invalid = record_again(seal, total_trajectories=4319)
    else:
        models = copy.deepcopy(seal["models"])
        models[-1]["seed"] = models[-2]["seed"]
        invalid = record_again(seal, models=models)
    path = tmp_path / "invalid_seal.json"
    p.write_once(path, invalid)
    with pytest.raises(ValueError, match="all_six_models"):
        confirm.require_generation_seal(tmp_path, frozen, manifest, path)


def test_changed_generation_file_cannot_acquire_private_assets(tmp_path, monkeypatch):
    frozen, manifest, seal, path = seal_fixture(tmp_path)
    source_path = Path(seal["models"][-1]["generation_manifest_path"])
    source_path.write_bytes(b"tampered")
    monkeypatch.setattr(
        confirm, "_check_protocol", lambda *args, **kwargs: (frozen["confirm_views"], rows())
    )
    monkeypatch.setattr(
        confirm.compiler, "modules", lambda _: pytest.fail("private capability opened")
    )
    with pytest.raises(ValueError, match="sealed_manifest_bytes"):
        confirm.offline_assets(tmp_path, frozen, manifest, path)


def test_scoring_initializer_changes_only_private_data_route(tmp_path, monkeypatch):
    feedback = SimpleNamespace(_SCORING=None)
    monkeypatch.setitem(sys.modules, "fixed_kernel_anchored_feedback_20260916", feedback)
    runtime = object()
    monkeypatch.setattr(confirm.views, "build_runtime", lambda: runtime)
    private = dict(
        source_manifest_id="manifest",
        confirm_bundles_opened=720,
        bundles={row["task_id"]: {} for row in rows()},
        generation_seal_id="B_confirm_generation_seal:sealed",
        sealed_point_ids=["point"],
    )
    confirm.initialize_scoring(tmp_path, private, "manifest", "point")
    assert feedback._SCORING == (tmp_path, private, "manifest", "point", False, runtime, {})
