"""Exact frozen old-qualification controls; no semantic reassessment or GPU."""

import copy

import pytest
from test_qa_vnext_fixed_kernel_materials import CODE, inputs, rerecord, token_assets

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    completion_materialize as parallel,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    materials as m,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    protocol as p,
)

NEW_CODE = "synthetic_completion_code_snapshot"


def binding(reg, session, qualification):
    return p.record(
        "material_qualification_lineage_binding",
        registered_session_id=reg["session_id"],
        material_session_id=session["id"],
        qualification_id=qualification["id"],
        code_snapshot_id=qualification["code_snapshot_id"],
    )


def test_old_qualification_bytes_and_assessor_identity_are_preserved():
    reg, session, qualification, _ = inputs()
    assets, tokenizer = token_assets()
    before = copy.deepcopy(qualification)
    lineage = binding(reg, session, qualification)
    result = m.materialize_session(
        session,
        reg,
        qualification,
        assets,
        tokenizer,
        code_snapshot_id=NEW_CODE,
        qualification_lineage_binding=lineage,
    )
    package = result["package"]
    assert qualification == before
    assert package["consumable"]
    assert package["code_snapshot_id"] == NEW_CODE
    assert package["qualification_code_snapshot_id"] == CODE
    assert package["qualification_id"] == qualification["id"]
    assert package["qualification_lineage_binding_id"] == lineage["id"]


def test_old_code_is_not_an_implicit_global_whitelist():
    reg, session, qualification, _ = inputs()
    assets, tokenizer = token_assets()
    with pytest.raises(ValueError, match="frozen_assessor_code"):
        m.materialize_session(
            session, reg, qualification, assets, tokenizer, code_snapshot_id=NEW_CODE
        )


@pytest.mark.parametrize(
    "field",
    ["registered_session_id", "material_session_id", "qualification_id", "code_snapshot_id"],
)
def test_lineage_cannot_authorize_other_slots_or_qualifications(field):
    reg, session, qualification, _ = inputs()
    lineage = rerecord(binding(reg, session, qualification), **{field: "substituted"})
    assets, tokenizer = token_assets()
    with pytest.raises(ValueError, match="exact_inherited_qualification_lineage"):
        m.materialize_session(
            session,
            reg,
            qualification,
            assets,
            tokenizer,
            code_snapshot_id=NEW_CODE,
            qualification_lineage_binding=lineage,
        )


def test_full_materializer_keeps_original_role_and_qualifications(tmp_path, monkeypatch):
    data = [inputs(replicate=0), inputs(replicate=12)]
    registry = p.record(
        "material_registry",
        sessions=[row[0] for row in data],
        session_count=2,
        freeze_id=data[0][0]["freeze_id"],
    )
    monkeypatch.setattr(p, "SESSION_CAP", 2)
    by_id = {
        reg["session_id"]: {"session": session, "qualification": q} for reg, session, q, _ in data
    }
    lineage = {reg["session_id"]: binding(reg, session, q) for reg, session, q, _ in data}
    index = m.materialize_all(
        registry,
        [{"session_id": reg["session_id"], "status": "finished"} for reg, *_ in data],
        tmp_path,
        tmp_path,
        code_snapshot_id=NEW_CODE,
        item_loader=lambda row: by_id[row["session_id"]],
        loader=lambda _: token_assets(),
        qualification_lineage_bindings=lineage,
    )
    outcomes = m.hydrate_outcomes(index, tmp_path)
    assert [row["role"] for row in outcomes] == ["train", "sealed"]
    assert [row["qualification_id"] for row in outcomes] == [row[2]["id"] for row in data]
    assert all(row["consumable"] for row in outcomes)
    assert index["inherited_qualification_bytes_rewritten"] is False


def cpu_control_loader(_):
    return token_assets()


def stored_inputs(output, data, *, preflight=True):
    rows = []
    for reg, session, qualification, _ in data:
        row = {"session_id": reg["session_id"], "status": "finished"}
        for key, value in (("session", session), ("qualification", qualification)):
            path = output / "sessions" / reg["session_id"] / (key + ".json")
            p.write_once(path, value)
            row[key] = m._reference(path, value, output)
        rows.append(row)
    if preflight:
        p.write_once(output / "tokenizer_binding_preflight.json", token_assets()[0])
    return rows


def test_serial_and_parallel_packages_are_identical(tmp_path, monkeypatch):
    data = [inputs(replicate=0), inputs(replicate=12)]
    monkeypatch.setattr(p, "SESSION_CAP", 2)
    registry = p.record(
        "material_registry",
        sessions=[row[0] for row in data],
        session_count=2,
        freeze_id=data[0][0]["freeze_id"],
    )
    lineage = {reg["session_id"]: binding(reg, session, q) for reg, session, q, _ in data}
    values = []
    for workers in (1, 2):
        output = tmp_path / str(workers)
        rows = stored_inputs(output, data)
        index = parallel.materialize_all(
            registry,
            rows,
            tmp_path,
            output,
            code_snapshot_id=NEW_CODE,
            qualification_lineage_bindings=lineage,
            workers=workers,
            loader=cpu_control_loader,
        )
        values.append((index, m.hydrate_outcomes(index, output)))
    serial, concurrent = values
    assert serial[0]["entries"] == concurrent[0]["entries"]
    assert serial[1] == concurrent[1]
    assert serial[0]["counts"] == concurrent[0]["counts"]
    assert concurrent[0]["CPU_encoding_workers"] == 2
    assert 1 <= concurrent[0]["tokenizer_loads"] <= 2
    assert concurrent[0]["token_arrays_transferred_between_processes"] is False


def test_parallel_global_gate_failure_never_loads_tokenizer_or_starts_workers(
    tmp_path, monkeypatch
):
    data = [inputs(replicate=0)]
    monkeypatch.setattr(p, "SESSION_CAP", 1)
    registry = p.record(
        "material_registry",
        sessions=[data[0][0]],
        session_count=1,
        freeze_id=data[0][0]["freeze_id"],
    )
    reg, session, qualification, _ = data[0]
    rows = stored_inputs(tmp_path, data, preflight=False)
    monkeypatch.setattr(parallel, "ProcessPoolExecutor", lambda **_: pytest.fail("no process"))
    index = parallel.materialize_all(
        registry,
        rows,
        tmp_path,
        tmp_path,
        code_snapshot_id=NEW_CODE,
        qualification_lineage_bindings={reg["session_id"]: binding(reg, session, qualification)},
        collection_gate_passed=False,
        workers=24,
        loader=lambda _: pytest.fail("no tokenizer"),
    )
    assert index["status"] == "NOT_MEASURED_GLOBAL_GATE"
    assert index["tokenizer_loads"] == 0
    assert not index["materialization_permitted"]
