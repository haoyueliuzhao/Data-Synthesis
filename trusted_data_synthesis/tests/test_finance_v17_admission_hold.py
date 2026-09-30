"""An explicit semantic hold blocks every training handoff before material/tensors."""

import pytest

from trusted_synthesis.finance_research import v17_material as material
from trusted_synthesis.finance_research.v6_collection import bound, persist
from trusted_synthesis.finance_research.v13_material_registration import entry


def held_material(tmp_path):
    registration = dict(id="original-registration")
    binding_path = tmp_path / "material/binding/record.json"
    persist(
        binding_path.parent, bound(dict(schema=material.BINDING_SCHEMA, registration=registration))
    )
    hold = bound(
        dict(
            schema="v17_explicit_semantic_admission_hold.v1",
            revoked_binding=entry(binding_path),
            registration=registration,
            original_prefix_must_continue=True,
            no_replacement_partition_or_chi_supplied=True,
        )
    )
    persist(tmp_path / "admission_hold", hold)
    return binding_path, hold


def test_held_pool_rejected_before_material_loader(monkeypatch, tmp_path):
    path, hold = held_material(tmp_path)
    monkeypatch.setattr(
        material.shared,
        "load_training_pool",
        lambda *a, **kw: pytest.fail("material must not load"),
    )
    with pytest.raises(ValueError, match="semantic admission hold"):
        material.load_training_pool(path)
    assert material.check_admission_hold(tmp_path, reject=False) == hold


def test_held_migration_rejected_before_registration_or_tensors(monkeypatch, tmp_path):
    from trusted_synthesis.finance_research import v17_continuation as continuation

    held_material(tmp_path)
    monkeypatch.setattr(
        continuation.shared,
        "register_and_migrate",
        lambda *a, **kw: pytest.fail("migration must not start"),
    )
    with pytest.raises(ValueError, match="semantic admission hold"):
        continuation.register_and_migrate(tmp_path, allowed_gpu_indices=[0])


def test_held_workflow_stops_before_any_other_material_or_prefix_check(monkeypatch, tmp_path):
    from trusted_synthesis.finance_research import v17_workflow as workflow

    _, hold = held_material(tmp_path)
    ctl = workflow.Supervisor.__new__(workflow.Supervisor)
    ctl.output, ctl.stop = tmp_path, False
    ctl.workflow = dict(original_prefix_root="unchanged-prefix")
    statuses = []
    ctl.update = lambda phase, **kwargs: statuses.append((phase, kwargs))
    monkeypatch.setattr(
        workflow.shared,
        "marker_complete",
        lambda *a: pytest.fail("no material or prefix checks before hold"),
    )
    assert ctl.wait_for_inputs() is False
    assert statuses[-1][0] == "SEMANTIC_HOLD_PREFIX_UNTOUCHED"
    assert statuses[-1][1]["revoked_binding"] == hold["revoked_binding"]
    assert statuses[-1][1]["original_prefix_control_untouched"] is True
