"""Lossless publication controls over synthetic files, never real credentials."""

import gzip
import json
import struct
import tarfile
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import publish as pub

SECRET = b"SYNTHETIC_TEST_SECRET_DO_NOT_PUBLISH"


def rewrite(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else p.encode(value))


def rerecord(row, **updates):
    return p.record(
        row["schema_version"].split(".")[-1],
        **{
            **{key: value for key, value in row.items() if key not in {"id", "schema_version"}},
            **updates,
        },
    )


def materials_source(tmp_path):
    code, data = tmp_path / "code", tmp_path / "data"
    root = code / p.OUTPUT
    root.mkdir(parents=True)
    data.mkdir()
    frozen = p.record("synthetic_study_freeze", test_only=True)
    population = p.record("population", tasks=[{"task_id": f"t{i}"} for i in range(200)])
    registry = p.record(
        "material_registry",
        freeze_id=frozen["id"],
        population_id=population["id"],
        session_count=10240,
        sessions=[{"session_id": f"s{i:05d}"} for i in range(10240)],
    )
    generation = p.record(
        "material_generation_report",
        generation_closed=True,
        no_inflight_requests=True,
        registered_sessions=10240,
        finished_sessions=0,
        unrequested_sessions=10240,
        status="STOP_INCOMPLETE_OR_CONTRACT",
    )
    budget = p.record(
        "kernel_budget_finalization",
        purpose_closed=True,
        report_id=generation["id"],
        freeze_id=frozen["id"],
    )
    index = p.record(
        "materialization_index",
        registry_id=registry["id"],
        freeze_id=frozen["id"],
        complete_registered_denominator=10240,
        collection_complete=False,
        entries=[
            {"registered_session_id": row["session_id"], "outcome": None, "package": None}
            for row in registry["sessions"]
        ],
    )
    values = {
        "freeze.json": frozen,
        "population.json": population,
        "registry.json": registry,
        "generation_report.json": generation,
        "budget_finalization.json": budget,
        "materialization_index.json": index,
        "material_gate.json": {"status": "FAIL", "scientific_results": "NOT_MEASURED"},
        "session_results.json": [
            {"session_id": row["session_id"], "status": "not_run"} for row in registry["sessions"]
        ],
        "duplicate_a.json": {"same": "original bytes"},
        "duplicate_b.json": {"same": "original bytes"},
        "events.jsonl": p.encode({"event": 1}) + b"\r\n" + p.encode({"event": 2}) + b"\n",
        "tests.xml": b'<testsuite tests="1" failures="0"/>',
        "console.log": SECRET,
    }
    for name, value in values.items():
        rewrite(root / name, value)
    return code, data, root


def seal(code, data, **kwargs):
    return pub.seal_stage(code, data, secret_loader=lambda _: SECRET, workers=2, **kwargs)


def pages(destination, references):
    result = []
    for reference in references:
        raw = (destination / reference["path"]).read_bytes()
        assert p.sha(raw) == reference["sha256"]
        result += json.loads(raw)["rows"]
    return result


def test_closed_STOP_can_publish_full_denominator_without_claiming_training(tmp_path):
    code, data, root = materials_source(tmp_path)
    student = root / "student_execution/future_result.json"
    rewrite(student, {"must_not_read_before_material_seal": SECRET.decode()})
    originals = {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }
    value = seal(code, data)
    destination = code / (p.OUTPUT + "_publication") / "materials"
    assert value["closure"]["registered_denominator"] == 10240
    assert value["closure"]["report_status"] == "STOP_INCOMPLETE_OR_CONTRACT"
    assert value["publication_is_scoped_evidence_not_a_scientific_PASS"]
    assert not value["original_source_files_modified"] and value["credential_hits"] == 0
    assert any(
        row["path"] == "student_execution" and row["contents_read"] is False
        for row in value["excluded_local_entries"]
    )
    assert any(row["path"] == "console.log" for row in value["excluded_local_entries"])
    members = pages(destination, value["member_index_pages"])
    assert {row["path"] for row in members} == set(originals) - {
        "console.log",
        "student_execution/future_result.json",
    }
    assert all(row["logical_reconstruction_SHA_verified"] for row in members)
    assert value["duplicate_original_path_count"] >= 1
    assert all((root / name).read_bytes() == raw for name, raw in originals.items())
    assert all(SECRET not in path.read_bytes() for path in destination.glob("*.json"))


def test_same_source_bytes_produce_same_deterministic_tar_and_indices(tmp_path):
    left = materials_source(tmp_path / "left")
    right = materials_source(tmp_path / "right")
    first, second = seal(*left[:2]), seal(*right[:2])
    assert first == second
    for reference in first["archives"]:
        assert reference["raw_tar_bytes"] <= pub.MAX_SHARD_BYTES
        assert reference["bytes"] <= pub.MAX_SHARD_BYTES
    with pytest.raises(ValueError, match="exclusive_regular_stage_destination"):
        seal(*left[:2])


@pytest.mark.parametrize(
    "mutation",
    [
        "generation_open",
        "inflight",
        "budget_open",
        "wrong_report",
        "missing_terminal",
        "false_complete_prefix",
    ],
)
def test_unclosed_or_inconsistent_collection_cannot_seal(tmp_path, mutation):
    code, data, root = materials_source(tmp_path)
    if mutation in {"generation_open", "inflight", "false_complete_prefix"}:
        old = json.loads((root / "generation_report.json").read_bytes())
        updates = (
            {"generation_closed": False}
            if mutation == "generation_open"
            else {"no_inflight_requests": False}
            if mutation == "inflight"
            else {
                "status": "COMPLETE_FIXED_COLLECTION",
                "finished_sessions": 10240,
                "unrequested_sessions": 0,
            }
        )
        changed = rerecord(old, **updates)
        rewrite(root / "generation_report.json", changed)
        budget = json.loads((root / "budget_finalization.json").read_bytes())
        rewrite(root / "budget_finalization.json", rerecord(budget, report_id=changed["id"]))
    elif mutation in {"budget_open", "wrong_report"}:
        old = json.loads((root / "budget_finalization.json").read_bytes())
        rewrite(
            root / "budget_finalization.json",
            rerecord(
                old,
                **(
                    {"purpose_closed": False}
                    if mutation == "budget_open"
                    else {"report_id": "different_report"}
                ),
            ),
        )
    else:
        rows = json.loads((root / "session_results.json").read_bytes())
        rewrite(root / "session_results.json", rows[:-1])
    with pytest.raises(ValueError):
        seal(code, data)
    assert not (code / (p.OUTPUT + "_publication") / "materials").exists()


@pytest.mark.parametrize(
    "name,raw",
    [
        (".env", b"x"),
        ("runtime/state.json", b"{}"),
        ("wallet.sqlite3", b"SQLite format 3\0"),
        ("hidden.json", b"SQLite format 3\0"),
        ("base.safetensors", b"base weights"),
    ],
)
def test_wallet_runtime_credentials_and_unapproved_weights_never_published(tmp_path, name, raw):
    code, data, root = materials_source(tmp_path)
    rewrite(root / name, raw)
    with pytest.raises(ValueError):
        seal(code, data)


def test_symlink_is_rejected_before_reading_target(tmp_path):
    code, data, root = materials_source(tmp_path)
    target = tmp_path / "private.json"
    rewrite(target, {"secret": SECRET.decode()})
    (root / "linked.json").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        seal(code, data)


@pytest.mark.parametrize("raw", [b'{ "a":1}', b'{"a":1,"a":2}', b'{"a":NaN}', b"not JSON"])
def test_noncanonical_JSON_is_rejected_without_rewriting(tmp_path, raw):
    code, data, root = materials_source(tmp_path)
    rewrite(root / "bad.json", raw)
    with pytest.raises(ValueError, match="invalid_or_noncanonical_JSON"):
        seal(code, data)
    assert (root / "bad.json").read_bytes() == raw


def test_exact_secret_scan_never_echoes_secret_value(tmp_path):
    code, data, root = materials_source(tmp_path)
    rewrite(root / "leak.json", {"unexpected": SECRET.decode()})
    with pytest.raises(ValueError) as error:
        seal(code, data)
    assert SECRET.decode() not in str(error.value)
    assert not (code / (p.OUTPUT + "_publication") / "materials").exists()


def test_allowlist_cannot_omit_scientific_failure_evidence(tmp_path):
    code, data, root = materials_source(tmp_path)
    allowlist = sorted(pub.MATERIAL_REQUIRED)
    with pytest.raises(ValueError, match="cannot_drop_stage_scientific_evidence"):
        seal(code, data, allowlist=allowlist)


def test_large_logical_JSON_losslessly_fragments_without_changing_original(tmp_path):
    code, data, root = materials_source(tmp_path)
    raw = p.encode({"logical_journal_test_only": "x" * (33 * 1024 * 1024)})
    rewrite(root / "large_journal.json", raw)
    before = p.sha(raw)
    value = seal(code, data)
    destination = code / (p.OUTPUT + "_publication") / "materials"
    physical = pages(destination, value["physical_member_index_pages"])
    pieces = sorted(
        [row for row in physical if row["logical_path"] == "large_journal.json"],
        key=lambda row: row["logical_offset"],
    )
    assert len(pieces) == 3 and [row["logical_offset"] for row in pieces] == [
        0,
        16 * 1024 * 1024,
        32 * 1024 * 1024,
    ]
    reconstructed = []
    for row in pieces:
        with tarfile.open(destination / row["publication_archive"], "r:gz") as archive:
            reconstructed.append(archive.extractfile(row["path"]).read())
    assert b"".join(reconstructed) == raw
    assert p.sha(root / "large_journal.json") == before
    assert value["logical_files_fragmented"] == 1
    assert all(
        row["bytes"] <= pub.MAX_SHARD_BYTES and row["raw_tar_bytes"] <= pub.MAX_SHARD_BYTES
        for row in value["archives"]
    )
    assert all(
        len(gzip.decompress((destination / row["path"]).read_bytes())) == row["raw_tar_bytes"]
        for row in value["archives"]
    )


def test_fragment_offset_mutation_is_not_a_logical_roundtrip(tmp_path, monkeypatch):
    root, destination = tmp_path / "raw", tmp_path / "publication"
    root.mkdir()
    destination.mkdir()
    monkeypatch.setattr(pub, "MAX_SHARD_BYTES", 20480)
    monkeypatch.setattr(pub, "FRAGMENT_BYTES", 4096)
    rewrite(root / "large.json", {"payload": "x" * 25000})
    original = pub._scan_member(root, "large.json", SECRET, {})
    physical = pub._physical_members(root, [original], SECRET)
    for i, rows in enumerate(pub._partition(physical)):
        name = f"raw-{i:05d}.tar.gz"
        pub._pack(root, rows, destination / name, SECRET)
        for row in rows:
            row["publication_archive"] = name
    pub._logical_roundtrips(root, destination, [original], physical)
    physical[0]["logical_offset"] = 1
    with pytest.raises(ValueError, match="ordered_gapless_logical_reconstruction"):
        pub._logical_roundtrips(root, destination, [original], physical)


def results_source(code, root):
    base = Path("student_execution")
    study = json.loads((root / "freeze.json").read_bytes())["id"]
    frozen = p.record(
        "execution_freeze",
        output_directory=str(Path(p.OUTPUT) / base),
        study_freeze_id=study,
        kernel_id="synthetic_kernel",
    )
    decision = p.record("actual_direction_decision", actual_complete=True, selected_arm="alpha0")
    report = p.record(
        "execution_report",
        actual_complete=True,
        status="COMPLETE_NO_POSITIVE_DIRECTION",
        study_freeze_id=study,
        kernel_id="synthetic_kernel",
        decision_id=decision["id"],
        actual_training_runs=9,
        actual_evaluation_sessions=1620,
    )
    rewrite(root / base / "preparation/execution_freeze.json", frozen)
    rewrite(root / base / "decision.json", decision)
    rewrite(root / base / "report.json", report)
    header = p.encode(
        {
            "model.layers.0.self_attn.q_proj.lora_A": {
                "dtype": "F32",
                "shape": [1],
                "data_offsets": [0, 4],
            },
            "model.layers.0.self_attn.q_proj.lora_B": {
                "dtype": "F32",
                "shape": [1],
                "data_offsets": [4, 8],
            },
        }
    )
    binary = struct.pack("<Q", len(header)) + header + struct.pack("<ff", 0.0, 0.0)
    approved = []
    for arm in p.ARMS:
        for seed in p.SEEDS:
            folder = base / "training" / f"A_{arm}_{seed}"
            name = folder / "final_adapter.safetensors"
            rewrite(root / name, binary)
            row = p.record(
                "training_report",
                actual_complete=True,
                status="COMPLETE_FINAL_CHECKPOINT",
                optimizer_updates=400,
                epochs_completed=10,
                final_adapter_restored_identity_verified=True,
                pool="A",
                arm=arm,
                seed=seed,
                study_freeze_id=study,
                kernel_id="synthetic_kernel",
                checkpoint_id="synthetic_parameter_digest",
                final_adapter={
                    "path": "final_adapter.safetensors",
                    "bytes": len(binary),
                    "sha256": p.sha(binary),
                    "parameter_digest": "synthetic_parameter_digest",
                },
            )
            rewrite(root / folder / "report.json", row)
            approved.append(str(name))
    rewrite(root / base / "jobs/stdout.log", SECRET)
    rewrite(
        root / base / "manifest.json",
        p.record(
            "evaluation_manifest",
            report_id=report["id"],
            phase="fixed_kernel_value_execution",
            members=[{"path": "jobs/stdout.log", "local_only": True}],
        ),
    )
    return str(base / "report.json"), approved


def test_results_only_approved_final_adapters_and_previous_material_stage_unchanged(tmp_path):
    code, data, root = materials_source(tmp_path)
    material = seal(code, data)
    material_path = code / (p.OUTPUT + "_publication") / "materials/publication_manifest.json"
    before = material_path.read_bytes()
    report_path, approved = results_source(code, root)
    value = seal(
        code,
        data,
        stage="results",
        report_path=report_path,
        allowlist=["student_execution"],
        approved_adapter_paths=approved,
    )
    assert value["closure"]["report_status"] == "COMPLETE_NO_POSITIVE_DIRECTION"
    assert value["closure"]["source_execution_manifest_may_include_locally_retained_console_logs"]
    assert material_path.read_bytes() == before and json.loads(before) == material
    destination = code / (p.OUTPUT + "_publication") / "results"
    members = pages(destination, value["member_index_pages"])
    assert len([row for row in members if row["format"] == "safetensors"]) == 9
    assert not any(row["path"].endswith(".log") for row in members)


@pytest.mark.parametrize("mutation", ["not_complete", "unapproved_base", "missing_approval"])
def test_results_incomplete_or_unapproved_model_bytes_are_rejected(tmp_path, mutation):
    code, data, root = materials_source(tmp_path)
    report_path, approved = results_source(code, root)
    if mutation == "not_complete":
        old = json.loads((root / report_path).read_bytes())
        rewrite(root / report_path, rerecord(old, actual_complete=False))
    elif mutation == "unapproved_base":
        rewrite(root / "student_execution/model.safetensors", b"not an approved adapter")
    else:
        approved = approved[:-1]
    with pytest.raises(ValueError):
        seal(
            code,
            data,
            stage="results",
            report_path=report_path,
            allowlist=["student_execution"],
            approved_adapter_paths=approved,
        )
