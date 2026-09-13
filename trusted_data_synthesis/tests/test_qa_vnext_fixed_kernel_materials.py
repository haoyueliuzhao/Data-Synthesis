"""All material consumers tested with explicitly synthetic provider controls."""

import copy
from pathlib import Path

import pytest
from test_qa_vnext_basis_conditioned_tokens import MockTokenizer
from test_qa_vnext_catalog_bridge_worker import fixture

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.controls import (
    script_for_witness,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import materials as m
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import runtime
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.distribution import (
    canonical_state_id,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.source_boundary import (
    prepare_fixture,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.representation import (
    encode_original_candidate,
)

CODE = "synthetic-material-code-snapshot"


def origin_control(session, *_):
    return p.record(
        "material_origin_verification",
        session_id=session["id"],
        registered_session_id=session["registered_session_id"],
        status="PASS_AUTHENTIC_MATERIAL_PUBLIC_CHAIN",
        synthetic_test_hook_not_real_authentication=True,
    )


def inputs(*, replicate=0, extra=(), long=False):
    f = fixture()
    if long:
        f["bundle"]["public"]["question"] += " original public context" * 1800
        f["messages"][0]["content"] = p.encode(f["bundle"]["public"]).decode()
        f["identity"]["public_messages_sha256"] = p.sha(p.encode(f["messages"]))
    reg = p.record(
        "session_registration",
        session_id="synthetic_registered_" + str(replicate),
        identity=f["identity"],
        task_id=f["identity"]["task_id"],
        family=f["identity"]["family"],
        pool="A",
        role="train" if replicate < 12 else "sealed",
        replicate=replicate,
        freeze_id="synthetic_freeze",
        profile=p.TARGET_PROFILE,
        basis="movement",
        system_prompt_sha256=p.sha(p.system_prompt(p.TARGET_PROFILE, "movement")),
    )
    script = script_for_witness(f["bundle"], f["native_bindings"], "movement")
    queue = iter([*script[:-1], *extra, *script[-1:]])
    session = runtime.generate(
        f["messages"],
        f["identity"],
        registered=reg,
        provider=lambda *_: p.encode(next(queue)).decode(),
    )
    prepared = prepare_fixture(f)
    q = m.assess_material(
        session,
        reg,
        prepared,
        ledger=None,
        transport_directory=None,
        code_snapshot_id=CODE,
        origin_verifier=origin_control,
    )
    return reg, session, q, prepared


def token_assets():
    return {"id": "synthetic_cpu_tokenizer", "model_max_position_embeddings": 32768}, MockTokenizer(
        "synthetic-full-history-template"
    )


def rerecord(row, **updates):
    fields = {key: value for key, value in row.items() if key not in {"id", "schema_version"}}
    return p.record(row["schema_version"].split(".")[-1], **{**fields, **updates})


def test_original_success_targets_keep_failed_and_format_history_without_target_promotion():
    reg, session, q, _ = inputs(
        extra=[{"tool": "read_source", "arguments": {"source_id": "missing"}}, "not JSON"]
    )
    candidates = m.original_candidates(session, reg, q)
    expected = [
        event["response_index"]
        for event in session["events"]
        if event["final"] or event["tool_call"] and event["tool_call"]["status"] == "ok"
    ]
    assert [row["response_index"] for row in candidates] == expected
    assert len(candidates) == len(session["turns"]) - 2
    assert candidates[-1]["messages"] == session["turns"][-1]["input_messages"]
    assert any("not JSON" in row["content"] for row in candidates[-1]["messages"])
    assert any("unknown_public_source" in row["content"] for row in candidates[-1]["messages"])
    assert all(
        row["target_text"] == session["turns"][row["response_index"]]["raw_response"]
        for row in candidates
    )
    binding, tokenizer = token_assets()
    value = m.materialize_session(session, reg, q, binding, tokenizer, code_snapshot_id=CODE)
    package, outcome = value["package"], value["outcome"]
    p.checked(package, "encoded_original_package")
    assert outcome["consumable"] and package["consumable"]
    assert package["whole_package_target_tokens"] == sum(
        row["representation"]["target_token_count"] for row in package["rows"]
    )
    assert outcome["state_id"] == canonical_state_id(q["actual_method"], q["full_class"])
    assert not package["failed_responses_promoted_to_positive_targets"]


def test_original_encoder_output_is_retained_exactly_not_retokenized_or_remasked():
    reg, session, q, _ = inputs()
    binding, tokenizer = token_assets()
    calls = []

    def encode(*args, **kwargs):
        result = encode_original_candidate(*args, **kwargs)
        calls.append(copy.deepcopy(result))
        return result

    value = m.materialize_session(
        session, reg, q, binding, tokenizer, code_snapshot_id=CODE, encoder=encode
    )
    assert [row["representation"] for row in value["package"]["rows"]] == calls
    assert len(calls) == len(m.original_candidates(session, reg, q))
    assert not value["package"]["retokenization_or_mask_reconstruction"]


def test_single_encoding_error_fails_entire_package_without_dropping_other_rows():
    reg, session, q, _ = inputs()
    binding, tokenizer = token_assets()
    calls = []

    def encode(candidate, *args, **kwargs):
        calls.append(candidate["id"])
        if len(calls) == 2:
            raise ValueError("synthetic boundary failure")
        return encode_original_candidate(candidate, *args, **kwargs)

    value = m.materialize_session(
        session, reg, q, binding, tokenizer, code_snapshot_id=CODE, encoder=encode
    )
    assert not value["outcome"]["consumable"]
    package = value["package"]
    assert len(package["errors"]) == 1 and len(package["rows"]) == len(calls)
    assert package["rows"][-1]["candidate"]["response_kind"] == "Final"
    assert package["whole_package_target_tokens"] is None
    assert package["rows"][1]["representation"]["original_candidate_retained"]
    assert not package["truncation"]


def test_overlength_rows_are_retained_as_original_not_fit_records():
    reg, session, q, _ = inputs(long=True)
    binding, tokenizer = token_assets()
    value = m.materialize_session(session, reg, q, binding, tokenizer, code_snapshot_id=CODE)
    package = value["package"]
    assert not package["consumable"]
    assert len(package["rows"]) == len(m.original_candidates(session, reg, q))
    assert all(row["representation"]["sequence_length"] > p.SEQUENCE_CAP for row in package["rows"])
    assert all(row["representation"]["input_ids"] is None for row in package["rows"])
    assert all(row["representation"]["truncated"] is False for row in package["rows"])
    assert package["whole_package_target_tokens"] > 0


def test_sealed_role_cannot_be_reassigned_to_train():
    reg, session, q, _ = inputs(replicate=12)
    binding, tokenizer = token_assets()
    value = m.materialize_session(session, reg, q, binding, tokenizer, code_snapshot_id=CODE)
    assert value["outcome"]["role"] == value["package"]["role"] == "sealed"
    with pytest.raises(ValueError):
        m.materialize_session(
            session, rerecord(reg, role="train"), q, binding, tokenizer, code_snapshot_id=CODE
        )


def test_origin_failure_cannot_be_overridden_by_callback_boolean():
    reg, session, _, prepared = inputs()

    def reject(*_):
        raise ValueError("synthetic receipt mismatch")

    q = m.assess_material(
        session,
        reg,
        prepared,
        ledger=None,
        transport_directory=None,
        code_snapshot_id=CODE,
        origin_verifier=reject,
    )
    assert q["financial_valid"] and not q["authentic_origin_verified"]
    assert not q["token_materialization_eligible"]
    assert (
        m.materialize_session(session, reg, q, None, None, code_snapshot_id=CODE)["package"] is None
    )
    forged = rerecord(q, authentic_origin_verified=True, token_materialization_eligible=True)
    with pytest.raises(ValueError, match="receipt_origin_not_boolean_self_attestation"):
        m.original_candidates(session, reg, forged)


def test_storage_contains_arrays_once_and_hydrates_exact_original_outcome(tmp_path):
    reg, session, q, _ = inputs()
    binding, tokenizer = token_assets()
    value = m.materialize_session(session, reg, q, binding, tokenizer, code_snapshot_id=CODE)
    entry = m.store_materialized(value, tmp_path)
    restored = m.hydrate_outcomes([entry], tmp_path)
    assert restored == [value["outcome"]]
    assert b'"input_ids"' not in (tmp_path / entry["outcome"]["path"]).read_bytes()
    assert b'"input_ids"' in (tmp_path / entry["package"]["path"]).read_bytes()
    changed = copy.deepcopy(entry)
    changed["outcome"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="original_artifact_bytes"):
        m.hydrate_outcomes([changed], tmp_path)


def test_full_denominator_required_before_any_tokenizer_or_candidate_work(tmp_path):
    reg, _, _, _ = inputs()
    registry = p.record(
        "material_registry", sessions=[reg], session_count=1, freeze_id="synthetic_freeze"
    )

    def forbidden(*_):
        raise AssertionError("must not materialize incomplete registry")

    with pytest.raises(ValueError, match="full_registered_denominator"):
        m.materialize_all(
            registry,
            [{"session_id": reg["session_id"], "status": "finished"}],
            None,
            tmp_path,
            code_snapshot_id=CODE,
            item_loader=forbidden,
            loader=forbidden,
        )


@pytest.mark.parametrize("incomplete", [False, True, "external_contract_failure"])
def test_batch_single_CPU_tokenizer_load_all_roles_and_no_success_prefix(
    tmp_path, monkeypatch, incomplete
):
    # A tiny in-memory control uses the same batch path; production retains the
    # literal 10,240 registry guard tested above and never changes that constant.
    values = [inputs(replicate=replicate) for replicate in (0, 12)]
    monkeypatch.setattr(p, "SESSION_CAP", 2)
    registry = p.record(
        "material_registry",
        sessions=[row[0] for row in values],
        session_count=2,
        freeze_id="synthetic_freeze",
    )
    by_id = {row[0]["session_id"]: {"session": row[1], "qualification": row[2]} for row in values}
    terminals = [{"session_id": row[0]["session_id"], "status": "finished"} for row in values]
    if incomplete is True:
        terminals[-1]["status"] = "budget_aborted"
    calls = []

    def loader(root):
        calls.append(root)
        return token_assets()

    index = m.materialize_all(
        registry,
        terminals,
        "unused_root",
        tmp_path,
        code_snapshot_id=CODE,
        item_loader=lambda row: by_id[row["session_id"]],
        collection_gate_passed=incomplete != "external_contract_failure",
        collection_gate_reason="synthetic external contract STOP"
        if incomplete == "external_contract_failure"
        else None,
        loader=loader,
    )
    assert len(calls) == index["tokenizer_loads"] == (0 if incomplete else 1)
    assert index["collection_complete"] is (not incomplete)
    if incomplete == "external_contract_failure":
        assert index["raw_registry_complete"] is True
        assert index["generation_contract_passed"] is False
        assert index["status"] == "NOT_MEASURED_GLOBAL_GATE"
        assert index["counts"]["consumable_train"] is None
        assert index["materialization_permitted"] is False
    outcomes = m.hydrate_outcomes(index, tmp_path)
    assert [row["role"] for row in outcomes] == ["train", "sealed"]
    if incomplete == "external_contract_failure":
        assert all(
            row["status"] == "finished"
            and row["consumability_status"] == "NOT_MEASURED_GLOBAL_GATE"
            and row["financial_valid"]
            for row in outcomes
        )
    assert all(row["consumable"] is (not incomplete) for row in outcomes)
    assert (
        all(row["original_package"] is None for row in outcomes)
        if incomplete
        else all(row["original_package"] for row in outcomes)
    )


def test_real_local_Qwen_tokenizer_consumes_same_public_package_without_weights():
    data_root = Path("/data1/zhuxinrui/projects/Data-Synthesis")
    if not (data_root / "trusted_data_synthesis/config/vtdo_qwen2_5_7b_500k.json").is_file():
        pytest.skip("separately pinned tokenizer/config assets unavailable")
    reg, session, q, _ = inputs()
    binding, tokenizer = m.load_local_tokenizer(data_root)
    value = m.materialize_session(session, reg, q, binding, tokenizer, code_snapshot_id=CODE)
    assert value["package"]["consumable"]
    assert binding["weights_are_members"] is False and binding["language_model_loaded"] is False
    assert value["package"]["maximum_sequence_length"] == 24576
