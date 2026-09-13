"""Two actual torch CPU outer boundaries; no financial experiment or Qwen load."""

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from test_qa_vnext_anchored_feedback import MockTokenizer, make_probe
from test_qa_vnext_anchored_state_catalog import toy_materials as toy_materials

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import (
    feedback,
    gradients,
    state_materials,
    study,
)
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import protocol as p


class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.table = torch.nn.Parameter(torch.arange(35, dtype=torch.float32).reshape(5, 7) / 70)

    def forward(self, input_ids, attention_mask=None, use_cache=False, logits_to_keep=None):
        assert use_cache is False
        logits = self.table[input_ids.cumsum(-1) % 5]
        return SimpleNamespace(
            logits=logits if logits_to_keep is None else logits[:, logits_to_keep, :]
        )


class Tokenizer(MockTokenizer):
    def decode(self, content, skip_special_tokens, clean_up_tokenization_spaces):
        assert not skip_special_tokens and not clean_up_tokenization_spaces
        return json.dumps({"final": {"answer": int(1 in content)}, "synthetic_control": True})


def dev_tasks():
    return [
        {"task_id": "task_" + f"{i:064x}", "group": group}
        for i, group in enumerate(group for group in feedback.GROUPS for _ in range(60))
    ]


def collector(model, registry, identity, policy):
    return [make_probe(model, Tokenizer(), identity, policy, row) for row in registry["probes"]]


def qualifier(transcript):
    value = json.loads(transcript["turns"][-1]["raw_response"])["final"]["answer"]
    return {
        "qualification_id": p.record(
            "synthetic_qualification",
            transcript_sha=p.sha(p.encode(transcript)),
            rule="synthetic token-one indicator, not financial utility",
        )["id"],
        "status": "PASS" if value else "FAIL",
    }


@pytest.fixture(scope="module")
def executions(toy_materials):
    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    root, manifest, _, catalog, batch = toy_materials
    prior = state_materials.initial_distribution(catalog, pool="A")
    mu = {task: 1 / len(prior) for task in prior}
    controls = [row["task_id"] for row in batch["tasks"] if row["group"] == "control"]
    policy = feedback.decoder_policy(
        eos_token_ids=[0],
        pad_token_id=0,
        tokenizer_binding_id="CPU_mock_only",
        chat_template_sha256=p.sha(Tokenizer.chat_template),
    )
    result = {}
    try:
        for condition in p.CONDITIONS:
            model = Tiny()
            optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0)

            def load(pi):
                return state_materials.update_examples(
                    root, manifest, catalog, batch, pool="A", distribution=pi
                )

            def train_epoch(current, opt, pi, epoch):
                current.train()
                consumed = state_materials.execute_update(
                    current, opt, load(pi), batch, pool="A", catalog=catalog, distribution=pi
                )
                return {
                    "epoch": epoch,
                    "execution_kind": "synthetic_cpu_control",
                    "consumption": consumed,
                }

            original_ids = [row["package_id"] for row in load(prior)]
            result[condition] = study.run_two_round_cpu(
                model,
                optimizer,
                pool="A",
                condition=condition,
                training_seed=11,
                prior=prior,
                mu=mu,
                control_tasks=controls,
                catalog=catalog,
                manifest=manifest,
                package_loader=load,
                train_epoch=train_epoch,
                dev_tasks=dev_tasks(),
                decoder_policy=policy,
                probe_collector=collector,
                probe_qualifier=qualifier,
                expected_package_ids=original_ids,
            )
        destination = os.environ.get("ANCHORED_CPU_EVIDENCE_DIRECTORY")
        if destination:
            destination = Path(destination).resolve()
            allowed = Path.cwd().resolve() / p.OUTPUT
            assert destination.is_relative_to(allowed)
            for condition, value in result.items():
                p.write_once(destination / (condition + ".json"), value)
        yield result
    finally:
        torch.set_num_threads(old_threads)


def test_new_comparison_is_fixed_full_algorithm_not_three_point_selection():
    plan = study.comparison_plan()
    assert plan["training_protocols"] == 15 and plan["feedback_sessions"] == 6480
    assert plan["final_greedy_sessions"] == 10260 and plan["total_local_Student_sessions"] == 16740
    assert (
        plan["primary_condition"] == "full_anchored_vtdo" and not plan["GPU_execution_authorized"]
    )
    assert all(row["condition"] != "c_only_anchored" for row in plan["runs"] if row["pool"] == "B")
    assert sum(row["feedback_sessions"] for row in plan["runs"] if row["pool"] == "B") == 2160


def test_two_real_CPU_boundaries_and_optimizer_state(executions):
    result = executions["full_anchored_vtdo"]
    assert result["outer_updates"] == 2 and result["inner_epochs"] == 10
    assert [row["epoch_boundary"] for row in result["rounds"]] == [0, 5]
    assert set(result["rounds"][0]["tensor_evidence"]["Adam_steps"].values()) == {0}
    assert set(result["rounds"][1]["tensor_evidence"]["Adam_steps"].values()) == {5}
    assert len(result["inner_epoch_records"]) == 10
    assert all(
        row["consumption"]["packages_completed"] == 64
        and row["consumption"]["optimizer_step_calls"] == 1
        for row in result["inner_epoch_records"]
    )
    assert not result["actual_Qwen_or_financial_utility_run"]
    assert not result["formal_population_or_token_budget_claimed"]


def test_round_has_actual_current_point_probabilities_C_and_anchors(executions):
    result = executions["full_anchored_vtdo"]
    for index, round_ in enumerate(result["rounds"]):
        assert len(round_["probe_originals"]) == 360
        assert round_["feedback_gradient_evidence"]["fixed_denominator"] == 360
        assert round_["work_accounting"]["registered_probe_sessions"] == 360
        assert round_["tensor_evidence"]["aggregate_G"]
        assert round_["tensor_evidence"]["reward_gradient"]
        update = round_["distribution_update"]
        assert update["maximum_optimality_residual"] < 1e-8
        assert update["probability_clipping_or_repair"] is False
        assert max(map(abs, round_["centered_Contribution"]["center_residuals"].values())) < 1e-8
        assert all(abs(sum(values.values()) - 1) < 1e-12 for values in update["pi_next"].values())
        if index == 0:
            assert all(
                value == 0
                for row in update["task_diagnostics"].values()
                for value in row["N"].values()
            )
        assert not round_["actual_financial_VTDO_round"]


def test_first_common_random_round_then_novelty_changes_second_update(executions):
    first = executions["c_only_anchored"]
    full = executions["full_anchored_vtdo"]
    assert first["rounds"][0]["probe_registry"] == full["rounds"][0]["probe_registry"]
    for task, values in first["rounds"][0]["distribution_update"]["pi_next"].items():
        for state, probability in values.items():
            assert probability == pytest.approx(
                full["rounds"][0]["distribution_update"]["pi_next"][task][state], abs=1e-14
            )
    assert first["rounds"][1]["distribution_update"]["contribution_exponent"] == 0.8
    assert first["rounds"][1]["distribution_update"]["effective_novelty_exponent"] == 0
    assert full["rounds"][1]["distribution_update"]["effective_novelty_exponent"] == 0.2
    assert any(
        value > 0
        for row in full["rounds"][1]["distribution_update"]["task_diagnostics"].values()
        for value in row["N"].values()
    )


def test_static_baseline_has_no_feedback_and_controls_stay_at_prior(executions):
    static = executions["static_alpha0"]
    full = executions["full_anchored_vtdo"]
    assert static["rounds"] == [] and static["outer_updates"] == 0
    for task in ("c0", "c1"):
        assert full["final_distribution"][task] == static["final_distribution"][task]


def test_missing_fixed_package_stops_before_feedback(toy_materials):
    root, manifest, _, catalog, batch = toy_materials
    pi = state_materials.initial_distribution(catalog, pool="A")
    packages = state_materials.update_examples(
        root, manifest, catalog, batch, pool="A", distribution=pi
    )
    with pytest.raises(ValueError, match="all_original_package_order"):
        study._check_packages(packages[:-1], [row["package_id"] for row in packages], pi, pool="A")


def test_virtual_buffers_are_bound_in_probability_point():
    from test_qa_vnext_anchored_gradients_isolation import Tiny as Buffered

    real = Buffered()
    virtual = gradients.FunctionalStudent(real, {"theta": real.theta.detach().clone()})
    point = feedback.bind_virtual_model(
        virtual, base_identity={"CPU_only": True}, virtual_step_id="step"
    )
    assert point["parameter_snapshot"]["buffers"]
    virtual._buffer_copies["scale"].add_(1)
    with pytest.raises(ValueError, match="parameter_bytes_changed"):
        feedback.validate_virtual_model(virtual, point)


def test_C_only_strength_not_renormalized_and_prior_not_optimized():
    plan = p.policy()
    assert plan["c_only_contribution_exponent_unchanged"] == 0.8
    assert plan["lambda_current"] == 4 and plan["lambda_prior"] == 1
    assert plan["prior"].startswith("r_h=pi_0")


@pytest.mark.parametrize("mutation", ["rows", "state"])
def test_same_package_ID_cannot_authorize_modified_content_or_state(toy_materials, mutation):
    root, manifest, _, catalog, batch = toy_materials
    pi = state_materials.initial_distribution(catalog, pool="A")
    packages = state_materials.update_examples(
        root, manifest, catalog, batch, pool="A", distribution=pi
    )
    ids = [row["package_id"] for row in packages]
    changed = copy.deepcopy(packages)
    if mutation == "rows":
        changed[0]["rows"][0]["representation"]["input_ids"][0] += 1
    else:
        changed[0]["state_id"] = next(
            key for key in pi[changed[0]["task_id"]] if key != changed[0]["state_id"]
        )
    with pytest.raises(ValueError, match="authenticated_original_rows"):
        study._authenticated_packages(
            changed, ids, pi, pool="A", catalog=catalog, manifest=manifest
        )


def _static_arguments(toy_materials):
    root, manifest, _, catalog, batch = toy_materials
    prior = state_materials.initial_distribution(catalog, pool="A")

    def loader(pi):
        return state_materials.update_examples(
            root, manifest, catalog, batch, pool="A", distribution=pi
        )

    return {
        "pool": "A",
        "condition": "static_alpha0",
        "training_seed": 11,
        "prior": prior,
        "mu": {task: 1 / 5 for task in prior},
        "control_tasks": ["c0", "c1"],
        "catalog": catalog,
        "manifest": manifest,
        "package_loader": loader,
        "dev_tasks": dev_tasks(),
        "decoder_policy": {},
        "probe_collector": None,
        "probe_qualifier": None,
        "expected_package_ids": [row["package_id"] for row in loader(prior)],
    }


@pytest.mark.parametrize("mutation", ["loader_pi", "training_pi", "external_prior", "fake_step"])
def test_callbacks_cannot_mutate_fixed_distribution_or_fake_training(toy_materials, mutation):
    arguments = _static_arguments(toy_materials)
    model = Tiny()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0)

    def change(pi):
        task = next(iter(pi))
        state = next(iter(pi[task]))
        pi[task][state] = 0.123

    original_loader = arguments["package_loader"]
    if mutation == "loader_pi":

        def loader(pi):
            loaded = original_loader(pi)
            change(pi)
            return loaded

        arguments["package_loader"] = loader

    def epoch(_model, _optimizer, pi, number):
        if mutation == "training_pi":
            change(pi)
        if mutation == "external_prior":
            change(arguments["prior"])
        return {"epoch": number, "execution_kind": "synthetic_cpu_control"}

    arguments["train_epoch"] = epoch
    expected = {
        "loader_pi": "loader_changed",
        "training_pi": "callback_changed",
        "external_prior": "fixed_prior",
        "fake_step": "not_self_attestation",
    }[mutation]
    with pytest.raises(ValueError, match=expected):
        study.run_two_round_cpu(model, optimizer, **arguments)


def test_static_branch_also_has_hard_CPU_gate(toy_materials):
    arguments = _static_arguments(toy_materials)
    arguments["train_epoch"] = lambda *args: pytest.fail("must reject before callbacks")
    model = Tiny().to("meta")
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    with pytest.raises(ValueError, match="CPU_only"):
        study.run_two_round_cpu(model, optimizer, **arguments)


def test_record_detaches_nested_mutable_inputs_and_old_rounds(executions):
    data = {"pi": {"x": {"z": 1.0}}}
    saved = p.record("immutable_input", value=data)
    data["pi"]["x"]["z"] = 0
    p.checked_record(saved, "immutable_input")
    original = executions["full_anchored_vtdo"]
    changed = copy.deepcopy(original)
    task = next(iter(changed["final_distribution"]))
    state = next(iter(changed["final_distribution"][task]))
    changed["final_distribution"][task][state] = 0
    for round_ in changed["rounds"]:
        p.checked_record(round_, "RoundArtifact")
