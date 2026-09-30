"""Small finite controls only; no wallet, paid requests, tokenizer, or device."""

import copy

from trusted_synthesis.finance_research import v14_material as material
from trusted_synthesis.finance_research import v14_workflow as workflow


def encoded(*, attempted=True, admitted=True):
    return dict(
        schema="synthetic_cache",
        encoding_started=attempted,
        encoding_admitted=admitted,
        layer_target_counts=dict(reason=2, tool=1, final=0) if admitted else {},
        original_public_content_characters=2,
        positive_public_content_characters=2,
        failures=[] if admitted else [dict(reason="synthetic_encoding_failure")],
    )


def test_encoding_progress_is_independent_of_missing_mapping():
    value = material.token_independent_profile(
        {"t": ["p", "q"]}, {"t": None}, {"p": encoded(), "q": encoded()}, []
    )
    profile = value["capability_profile"]
    assert profile["encoding_started_packages"] == 2
    assert profile["supervised_tokens"]["reason"] == 4
    assert profile["D_pi"] is None and profile["manual_intervention_dose"] is None
    assert not value["material_complete"] and not value["exploratory_training_admitted"]
    assert value["N"] == 1 and value["package_count"] == 2


def test_real_failure_and_pending_authority_are_not_both_called_unstarted():
    outcomes = {"p": encoded(admitted=False), "q": encoded(attempted=False, admitted=False)}
    value = material.token_independent_profile({"t": ["p", "q"]}, {"t": None}, outcomes, ["q"])
    profile = value["capability_profile"]
    assert profile["encoding_started_packages"] == 1
    assert profile["supervised_tokens"] is None
    assert value["candidate_slot_ids"] == ["p", "q"]
    assert not value["material_complete"]


def test_complete_support_preserves_singleton_and_exact_manual_dose():
    mappings = dict(
        a=dict(
            mapping_status="complete",
            deterministic_singleton=True,
            state_by_slot={"p": "only"},
            chi_by_state={"only": None},
            chi_status="not_required_for_weighting",
        ),
        b=dict(
            mapping_status="complete",
            deterministic_singleton=False,
            state_by_slot={"q": "z0", "r": "z1"},
            chi_by_state={"z0": 0, "z1": 1},
        ),
    )
    value = material.token_independent_profile(
        {"a": ["p"], "b": ["q", "r"]},
        mappings,
        {p: encoded() for p in ("p", "q", "r")},
        [],
    )
    profile = value["capability_profile"]
    assert value["material_complete"] and value["exploratory_training_admitted"]
    assert profile["D_pi"] == profile["chi_flexible_tasks"] == 1
    dose = profile["manual_intervention_dose"]
    assert dose["per_task"]["a"]["p"] is None
    assert dose["per_task"]["a"]["TV_plus"] == "0"
    assert dose["per_task"]["b"]["TV_plus"] == dose["per_task"]["b"]["TV_minus"] == "1/6"
    assert dose["mu_weighted_TV_plus"] == "1/12"


def test_character_inventory_union_does_not_modify_original_span_boundaries():
    spans = [
        dict(original_segment_id="u", start=0, end=3),
        dict(original_segment_id="u", start=2, end=5),
        dict(original_segment_id="v", start=0, end=2),
    ]
    original = copy.deepcopy(spans)
    assert material._char_union(spans) == 7
    assert spans == original


def test_derived_consumer_metadata_keeps_original_partition_and_chi(monkeypatch):
    original = dict(
        schema="v14_derived_mapping.v1",
        usable=True,
        slot_ids=["p", "q"],
        inspection=dict(
            mapping_status="complete",
            mapping_admitted=True,
            states=[dict(state_id="a", chi=0), dict(state_id="b", chi=1)],
            state_by_slot={"p": "a", "q": "b"},
            chi_by_state={"a": 0, "b": 1},
        ),
    )
    before = copy.deepcopy(original)
    monkeypatch.setattr(material, "read_ref", lambda ref: original)
    review = dict(
        mapping_authority_refs=[dict(task_id="t", record=dict(id="source"))],
        inherited_singleton_refs=[],
        residual_mapping_task_ids=[],
    )
    mappings, _ = material.task_mappings(review, {})
    value = material.token_independent_profile(
        {"t": ["p", "q"]}, mappings, {s: encoded() for s in ("p", "q")}, []
    )
    assert value["material_complete"] and mappings["t"]["deterministic_singleton"] is False
    assert original == before
    for key in ("states", "state_by_slot", "chi_by_state"):
        assert mappings["t"][key] == original["inspection"][key]


def test_partial_conditional_bounds_do_not_impute_unresolved_state_or_dose():
    mapped = dict(
        mapping_status="complete", state_by_slot={"p": "a", "q": "b"}, chi_by_state={"a": 0, "b": 1}
    )
    result = material.conditional_bounds({"t": ["p", "q"], "u": ["r", "s", "v"]}, {"t": mapped})
    assert result["D_pi_interval"] == [1, 3]
    assert result["multi_state_task_interval"] == result["chi_flexible_task_interval"] == [1, 2]
    assert result["known_mu_weighted_TV_plus"] == result["known_mu_weighted_TV_minus"] == "1/12"
    assert result["full_domain_measurements_replaced"] is False
    assert result["training_authorized"] is False


def test_failed_new_projection_has_no_old_failed_authority_fallback():
    review = dict(
        inherited_projection_authority_refs=[dict(slot_id="kept", record={"id": "old"})],
        derived_projection_authority_refs=[],
        residual_projection_slot_ids=["missing"],
    )
    new = {("projection", "missing"): dict(record=dict(inspection=dict(usable=False)))}
    assert set(material.projection_authorities(review, new)) == {"kept"}


def supervisor(tmp_path, monkeypatch):
    ctl = workflow.Supervisor.__new__(workflow.Supervisor)
    ctl.output, ctl.root = tmp_path, tmp_path / "workflow"
    ctl.plan = {"id": "synthetic", "protocol_identity": "synthetic"}
    ctl.workflow = {"allowed_gpu_indices": [0]}
    ctl.stop, ctl.children, ctl.max_gpu_workers = False, {}, 3
    phases = []
    ctl.update = lambda phase, **kwargs: phases.append((phase, kwargs))
    monkeypatch.setattr(workflow, "checked", lambda path: {"id": "synthetic"})
    ctl.run_mainline = lambda binding: (_ for _ in ()).throw(AssertionError("must not train"))
    return ctl, phases


def test_partial_parallel_stage_does_not_join_or_train(tmp_path, monkeypatch):
    ctl, phases = supervisor(tmp_path, monkeypatch)
    ctl.parallel_material_jobs = lambda: False
    ctl.plain_job = lambda *args: (_ for _ in ()).throw(AssertionError("no final join"))
    assert ctl.run() is None and not phases


def test_partial_join_does_not_load_or_train_successful_subset(tmp_path, monkeypatch):
    ctl, phases = supervisor(tmp_path, monkeypatch)
    ctl.parallel_material_jobs = lambda: True
    ctl.plain_job = lambda *args: True
    monkeypatch.setattr(material, "load_training_pool", lambda p: 1 / 0)
    assert ctl.run() is None
    assert phases[-1][0] == "BLOCKED_WHOLE_MATERIAL_SAVED"
    assert phases[-1][1]["no_prefix_training"]


def test_initial_cache_marker_uses_actual_revision_run(tmp_path, monkeypatch):
    from trusted_synthesis.finance_research import v14_encoding_cache

    result = dict(
        authority_revision=dict(id="revision-id"),
        known_authority_count=2465,
        pending_authority_slot_ids=["a", "b", "c"],
    )
    monkeypatch.setattr(v14_encoding_cache, "run", lambda *a, **k: result)
    observed = []
    monkeypatch.setattr(workflow, "entry", lambda path: observed.append(path) or {"id": "run-id"})
    monkeypatch.setattr(workflow, "persist", lambda *a: None)
    value = workflow.initial_encoding(tmp_path)
    assert observed == [tmp_path / "encoding_cache/runs/revision-id/record.json"]
    assert value["known_authority_count"] == 2465 and value["training_authorized"] is False
