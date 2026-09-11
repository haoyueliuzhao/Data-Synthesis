"""Frozen selection consumption controls using only the character tokenizer mock."""

import copy
import socket

import pytest
from test_qa_vnext_basis_conditioned_tokens import ROOT, MockTokenizer

from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support import (
    consumption,
    tokens,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.plan import (
    LABELS,
    SYSTEMS,
    condition,
    fixed_selection,
    record,
    sha,
)


@pytest.fixture(autouse=True)
def no_live_resources(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("consumption controls must not load a real tokenizer or network resources")

    monkeypatch.setattr(tokens.assets, "load_tokenizer", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


def audits():
    rows = []
    for label in LABELS:
        basis, task, replicate = label.split("_")
        rows.append(
            {
                "label": label,
                "arm": basis,
                "task_key": task,
                "replicate": int(replicate),
                "condition_id": condition(basis)["id"],
                "formula_driven_trace_verified": True,
                "full_mapping_status": "MAPPED",
                "class_id": "synthetic-new-class:" + label,
                "projection_id": "synthetic-new-projection:" + label,
                "method_record_id": "synthetic-method-record:" + label,
                # Both guidance conditions supply each actual method stratum. The
                # representation gate must not replace m with the requested g.
                "method_stratum": "movement" if int(replicate) % 2 else "endpoint",
            }
        )
    return rows


def reidentify(row):
    return record(
        row["id"].partition(":")[0],
        **{key: value for key, value in row.items() if key not in {"id", "schema_version"}},
    )


def package(label):
    basis, task, _ = label.split("_")
    messages = [
        {"role": "system", "content": SYSTEMS[basis]},
        {"role": "user", "content": "synthetic source task " + task},
    ]
    positives = []
    for index, (kind, target) in enumerate(
        (
            ("calculate", ' {"tool": "calculate", "arguments": {"expression": "1 + 2"}}\n'),
            ("Final", ' {"final": "原样 Unicode🙂", "value": 3.00 }\n'),
        )
    ):
        raw = target.encode()
        candidate = record(
            "basis_original_positive_candidate",
            population=basis,
            task_key=task,
            session_label=label,
            response_index=index,
            response_kind=kind,
            source_closeout_id="synthetic-audit:" + label,
            request_sha256=sha((label + str(index)).encode()),
            response_projection_sha256=sha(("synthetic projection " + label + str(index)).encode()),
            raw_response_sha256=sha(raw),
            input_messages=copy.deepcopy(messages),
            target_response=target,
        )
        positives.append((candidate, raw))
        messages.extend(
            [
                {"role": "assistant", "content": target},
                {"role": "user", "content": '{"tool_result":{"status":"ok","value":3}}'},
            ]
        )
    return positives


@pytest.fixture
def prepared():
    selection = fixed_selection(audits())
    pool = {item["label"]: package(item["label"]) for item in selection["selected"]}
    binding, policy = tokens.read_bound_metadata(ROOT)
    calls = []

    def loader(root):
        assert root == ROOT
        calls.append(root)
        return binding, policy, MockTokenizer(binding["chat_template"])

    return selection, pool, policy, loader, calls


def forbidden_loader(*args, **kwargs):
    pytest.fail("tokenizer must not load before all raw support and source gates pass")


def test_exact_selected_sixteen_checked_once_with_mixed_guidance_and_four_holdouts(
    prepared, monkeypatch
):
    selection, pool, policy, loader, calls = prepared
    original = copy.deepcopy((selection, pool))
    encoded_ids = []
    original_encoder = tokens.encode_candidate

    def tracked(candidate, *args):
        encoded_ids.append(candidate["id"])
        return original_encoder(candidate, *args)

    monkeypatch.setattr(tokens, "encode_candidate", tracked)
    result = consumption.check_selected(
        ROOT, selection, pool, loader=loader, expected_policy=policy
    )
    assert (selection, pool) == original
    assert result["status"] == "SUPPORT_REPRESENTATION_ESTABLISHED"
    assert len(calls) == result["tokenizer_load_attempts"] == 1
    assert result["tokenizer_loaded"] is True
    assert result["selected_original_packages"] == len(result["package_checks"]) == 16
    assert result["selected_future_train_packages"] == 12
    assert result["selected_heldout_packages"] == 4
    assert result["candidate_encoding_attempts"] == len(encoded_ids) == len(set(encoded_ids)) == 32
    assert result["selected_candidate_rows"] == 32
    assert result["all_selected_rows_checked"] is result["all_selected_packages_checked"] is True
    assert result["source_selection_id"] == selection["id"]
    assert result["failures"] == []
    assert {row["requested_basis"] for row in result["package_checks"]} == {"endpoint", "movement"}
    assert any(row["requested_basis"] != row["actual_method"] for row in result["package_checks"])
    assert sum(row["heldout_representation_only"] for row in result["package_checks"]) == 4
    for check in result["token_checks"]:
        assert check["representation"]["population"] == check["requested_basis"]
        assert check["representation"]["guidance_system_sha256"] == sha(
            SYSTEMS[check["requested_basis"]].encode()
        )
    for field in (
        "training_allowed",
        "training_weights_assigned",
        "training_population_27_materialized",
    ):
        assert result[field] is False
    for field in (
        "training_runs",
        "Student_weight_loads",
        "Student_forward_calls",
        "Student_generations",
        "NLL_calls",
        "greedy_calls",
        "heldout_training_NLL_or_greedy_calls",
        "Provider_calls",
        "historical_target_packages_consumed",
        "historical_token_arrays_read_or_retokenized",
    ):
        assert result[field] == 0


@pytest.mark.parametrize("ineligible", ["financial", "mapping", "method"])
def test_any_raw_stratum_below_four_keeps_empty_selection_and_zero_tokenizer(ineligible):
    rows = audits()
    affected = [
        row for row in rows if row["task_key"] == "X2" and row["method_stratum"] == "movement"
    ]
    for row in affected[3:]:
        if ineligible == "financial":
            row["formula_driven_trace_verified"] = False
            row["full_mapping_status"] = "NOT_ELIGIBLE"
        elif ineligible == "mapping":
            row["full_mapping_status"] = "UNDETERMINED"
        else:
            row["method_stratum"] = "MIXED"
    selection = fixed_selection(rows)
    # Even the candidate argument need not be accessed under raw insufficiency.
    result = consumption.check_selected(ROOT, selection, object(), loader=forbidden_loader)
    assert result["status"] == "INPUT_INADEQUATE"
    assert result["selected"] == result["token_checks"] == result["package_checks"] == []
    assert result["tokenizer_load_attempts"] == result["candidate_encoding_attempts"] == 0
    assert result["tokenizer_loaded"] is result["training_allowed"] is False


def test_extra_pool_packages_are_never_accessed_or_substituted(prepared):
    selection, pool, _, loader, _ = prepared
    unselected = next(label for label in LABELS if label not in pool)
    pool[unselected] = object()  # Would fail if the extra package were inspected.
    result = consumption.check_selected(ROOT, selection, pool, loader=loader)
    assert result["status"] == "SUPPORT_REPRESENTATION_ESTABLISHED"
    assert unselected not in {row["label"] for row in result["package_checks"]}
    missing = selection["selected"][0]["label"]
    del pool[missing]
    result = consumption.check_selected(ROOT, selection, pool, loader=forbidden_loader)
    assert result["status"] == "SELECTED_SOURCE_VALIDATION_FAILED"
    assert result["failures"][0]["label"] == missing
    assert result["token_checks"] == []


@pytest.mark.parametrize(
    "mutation", ["stale_id", "later_package", "heldout_role", "duplicate_method", "false_ready"]
)
def test_selection_identity_fixed_order_and_roles_cannot_be_changed(prepared, mutation):
    selection, pool, _, _, _ = prepared
    if mutation in {"stale_id", "later_package"}:
        chosen = selection["selected"][0]
        chosen["label"] = selection["eligible"][chosen["task_key"]][chosen["actual_method"]][4]
    elif mutation == "heldout_role":
        selection["selected"][3]["role"] = "future_train"
    elif mutation == "duplicate_method":
        selection["eligible"]["X1"]["movement"] = selection["eligible"]["X1"]["endpoint"]
    else:
        selection["eligible"]["X1"]["endpoint"] = selection["eligible"]["X1"]["endpoint"][:3]
    if mutation != "stale_id":
        selection = reidentify(selection)
    with pytest.raises(ValueError, match="consumption."):
        consumption.check_selected(ROOT, selection, pool, loader=forbidden_loader)


@pytest.mark.parametrize(
    "mutation",
    ["raw", "candidate_hash", "guidance", "session", "missing_Final", "duplicate_row", "history"],
)
def test_original_identity_bytes_guidance_and_complete_history_fail_before_loader(
    prepared, mutation
):
    selection, pool, _, _, _ = prepared
    label = selection["selected"][0]["label"]
    candidate, raw = pool[label][-1]
    if mutation == "raw":
        pool[label][-1] = (candidate, raw + b" ")
    elif mutation == "candidate_hash":
        candidate["target_response"] += " "
    elif mutation == "guidance":
        other = "movement" if candidate["population"] == "endpoint" else "endpoint"
        candidate["input_messages"][0]["content"] = SYSTEMS[other]
        pool[label][-1] = (reidentify(candidate), raw)
    elif mutation == "session":
        other = next(name for name in pool if name != label)
        pool[label] = pool[other]
    elif mutation == "missing_Final":
        pool[label].pop()
    elif mutation == "duplicate_row":
        pool[label].insert(0, pool[label][0])
    else:
        candidate["input_messages"][2]["content"] = "different previous assistant output"
        pool[label][-1] = (reidentify(candidate), raw)
    result = consumption.check_selected(ROOT, selection, pool, loader=forbidden_loader)
    assert result["status"] == "SELECTED_SOURCE_VALIDATION_FAILED"
    assert result["token_checks"] == []
    assert result["tokenizer_load_attempts"] == 0
    assert result["failures"][0]["label"] == label


def test_unconsumable_heldout_stops_gate_with_all_sixteen_checked_without_replacement(prepared):
    selection, pool, _, loader, calls = prepared
    label = next(item["label"] for item in selection["selected"] if item["role"] == "heldout")
    candidate, _ = pool[label][-1]
    candidate["target_response"] = "t" * 33_000
    raw = candidate["target_response"].encode()
    candidate["raw_response_sha256"] = sha(raw)
    pool[label][-1] = (reidentify(candidate), raw)
    before = copy.deepcopy((selection, pool))
    result = consumption.check_selected(ROOT, selection, pool, loader=loader)
    assert (selection, pool) == before
    assert result["status"] == "SELECTED_REPRESENTATION_FAILED"
    assert result["consumability_established"] is result["training_allowed"] is False
    assert len(calls) == 1 and result["candidate_encoding_attempts"] == 32
    assert len(result["package_checks"]) == 16
    assert len(result["failures"]) == 1
    assert result["failures"][0]["label"] == label
    failed = next(row for row in result["token_checks"] if row["status"] == "FAIL")
    assert failed["role"] == "heldout"
    assert failed["representation"]["reason"] == "maximum_sequence_length_exceeded"
    assert failed["representation"]["input_ids"] is None
    assert failed["representation"]["truncated"] is False


def test_single_encoding_failure_does_not_retry_or_replace_and_all_fixed_rows_attempt_once(
    prepared, monkeypatch
):
    selection, pool, _, loader, _ = prepared
    original = tokens.encode_candidate
    attempts = []

    def fail_first(candidate, *args):
        attempts.append(candidate["id"])
        if len(attempts) == 1:
            raise ValueError("basis_tokens.boundary_crossing")
        return original(candidate, *args)

    monkeypatch.setattr(tokens, "encode_candidate", fail_first)
    result = consumption.check_selected(ROOT, selection, pool, loader=loader)
    assert result["status"] == "SELECTED_REPRESENTATION_FAILED"
    assert len(attempts) == len(set(attempts)) == 32
    assert len(result["package_checks"]) == 16
    assert result["token_checks"][0]["representation"] is None
    assert result["failures"][0]["reason"] == "basis_tokens.boundary_crossing"


def test_loader_failure_stops_without_encoding_or_retry(prepared):
    selection, pool, _, _, _ = prepared
    attempts = []

    def fail(root):
        attempts.append(root)
        raise ValueError("tokenizer.binding_drift")

    result = consumption.check_selected(ROOT, selection, pool, loader=fail)
    assert result["status"] == "SELECTED_REPRESENTATION_FAILED"
    assert len(attempts) == result["tokenizer_load_attempts"] == 1
    assert result["tokenizer_loaded"] is False
    assert result["token_checks"] == []
    assert result["failures"][0]["phase"] == "tokenizer_loading"


def test_presealed_policy_mismatch_rejects_before_any_candidate_encoding(prepared, monkeypatch):
    selection, pool, policy, loader, _ = prepared
    changed = copy.deepcopy(policy)
    changed["training"] = True
    monkeypatch.setattr(tokens, "encode_candidate", forbidden_loader)
    result = consumption.check_selected(
        ROOT, selection, pool, loader=loader, expected_policy=changed
    )
    assert result["status"] == "SELECTED_REPRESENTATION_FAILED"
    assert result["token_checks"] == []
    assert result["failures"][0]["reason"] == "consumption.presealed_policy"
