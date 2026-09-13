"""Pure analysis and admission tests; all matrix data are scripted test fixtures."""

import copy
from pathlib import Path

import pytest
from test_qa_vnext_catalog_bridge_worker import fixture
from test_qa_vnext_probe_coverage_core import tasks

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.controls import (
    script_for_witness,
)
from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import (
    assessment,
    metrics,
    runtime,
    study,
)
from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import (
    protocol as p,
)


@pytest.fixture(scope="module")
def matrix():
    selected = tasks()
    for row in selected:
        f = fixture(row["family"], row["quantity"])
        row.update(
            {
                key: f["identity"][key]
                for key in ("surface_version_id", "public_messages_sha256", "parent_manifest_id")
            }
        )
    registry = p.make_registry(selected, "synthetic_analysis_only")
    results = []
    for reg in registry:
        f = fixture(reg["family"], reg["quantity"])
        f["identity"] = reg["identity"]
        f["bundle"]["task_id"] = reg["task_id"]
        actual = "movement" if reg["profile"] == "P2_method_delivery" else "endpoint"
        queue = iter(script_for_witness(f["bundle"], f["native_bindings"], actual))
        session = runtime.generate(
            f["messages"],
            f["identity"],
            registered=reg,
            provider=lambda *_, queue=queue: p.encode(next(queue)).decode(),
        )
        q = assessment.assess(
            session,
            f,
            {
                "session_id": session["id"],
                "status": "PASS_AUTHENTIC_PROBE_PUBLIC_CHAIN",
                "test_only_mock_authentication": True,
            },
        )
        results.append(
            {"registered_session_id": reg["session_id"], "session": session, "qualification": q}
        )
    return registry, results


def fake_loader(root):
    return {"id": "test_only_tokenizer", "model_max_position_embeddings": 32768}, None


def fake_encoder(row, binding, tokenizer, *, maximum_sequence_length):
    assert maximum_sequence_length == 24576
    assert p.sha(row["target_text"]) == row["target_raw_sha256"]
    return {
        "id": "mock_encoded:" + row["id"],
        "sequence_length": 100,
        "target_token_count": 10,
        "consumable_token_representation": True,
        "reason": None,
    }


def test_complete_matrix_counts_methods_not_guidance_and_is_not_training(matrix):
    registry, results = matrix
    pairs = [(x["session"], x["qualification"]) for x in results]
    tokens = assessment.token_diagnostics(
        pairs, None, complete_registry=True, loader=fake_loader, encoder=fake_encoder
    )
    value = metrics.summarize(registry, results, tokens)
    assert value["totals"]["registered_denominator"] == 144
    assert value["totals"]["token_consumable_movement"] == 48
    assert value["totals"]["token_consumable_endpoint"] == 96
    assert all(x["registered_denominator"] == 24 for x in value["by_profile_guidance"])
    assert not value["training_admitted"]
    assert all(not x["two_method_consumable_support"] for x in value["task_profile_coverage"])


def test_missing_and_reordered_rollouts_rejected(matrix):
    registry, results = matrix
    tokens = assessment.token_diagnostics([], None, complete_registry=False)
    with pytest.raises(ValueError):
        metrics.summarize(registry, results[:-1], tokens)
    with pytest.raises(ValueError):
        metrics.summarize(registry, list(reversed(results)), tokens)


def test_unrequested_remains_full_denominator_not_fabricated_zero_response(matrix):
    registry, results = matrix
    results = copy.deepcopy(results)
    results[0] = {
        "registered_session_id": registry[0]["session_id"],
        "session": None,
        "qualification": None,
    }
    tokens = assessment.token_diagnostics([], None, complete_registry=False)
    value = metrics.summarize(registry, results, tokens)
    assert value["totals"]["registered_denominator"] == 144 and value["totals"]["attempted"] == 143
    assert value["totals"]["actual_method_counts"]["NOT_REQUESTED"] == 1
    assert not value["all_registered_results"][0]["attempted"]


def test_token_error_retains_whole_package_and_does_not_truncate(matrix):
    pair = matrix[1][0]
    calls = []

    def encoder(row, *args, **kwargs):
        calls.append(row["response_index"])
        if len(calls) == 1:
            raise ValueError("test boundary failure")
        return fake_encoder(row, *args, **kwargs)

    value = assessment.token_diagnostics(
        [(pair["session"], pair["qualification"])],
        None,
        complete_registry=True,
        loader=fake_loader,
        encoder=encoder,
    )
    package = value["packages"][0]
    assert not package["consumable"] and not package["truncation"]
    assert package["complete_candidate_count"] == len(calls)
    assert len(package["errors"]) == 1
    assert not package["training_eligible"]


def test_serialized_scripted_control_checks_opposite_guidance_not_only_desired_state():
    f = fixture()
    value = study._control((f, "P2_method_delivery", "endpoint", "movement"))
    assert value["passed"] and value["actual_method"] == "movement"
    assert value["wire_body_rendered_but_HTTP_not_called"] and not value["authentic_Probe_data"]
    assert value["maximum_serialized_request_bytes"] < p.MAX_BODY_BYTES


@pytest.mark.parametrize(
    "mutation", ["same_root", "main_moved", "wrong_branch", "different_repository"]
)
def test_admission_root_isolation_before_any_write(tmp_path, monkeypatch, mutation):
    code, data = tmp_path / "code", tmp_path / "data"
    code.mkdir()
    data.mkdir()
    monkeypatch.setattr(study, "__file__", str(code / "module.py"))

    def fake_git(root, *args):
        if args == ("branch", "--show-current"):
            return ("main" if root == data or mutation == "wrong_branch" else p.BRANCH).encode()
        if args == ("rev-parse", "HEAD"):
            return ("wrong" if mutation == "main_moved" else p.MAIN_COMMIT).encode()
        return (str(root) if mutation == "different_repository" else "/shared.git").encode()

    monkeypatch.setattr(study, "git", fake_git)
    with pytest.raises(ValueError):
        study.guarded_roots(code, code if mutation == "same_root" else data)
    assert not (code / p.OUTPUT).exists()


def test_code_freeze_includes_new_source_and_tests():
    root = Path(study.__file__).resolve().parents[5]
    result = study.code_snapshot(root)
    assert len(result["members"]) >= 9
    assert any(x["path"].endswith("study.py") for x in result["members"])
    assert any("test_qa_vnext_probe_coverage_" in x["path"] for x in result["members"])
