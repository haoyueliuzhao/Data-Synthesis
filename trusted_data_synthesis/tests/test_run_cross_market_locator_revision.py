"""New finite execution credit and frozen parent checks; synthetic metadata only."""

import copy

import pytest
import run_cross_market_locator_revision_20260926 as m


def parents():
    parent = dict(
        id="prior",
        document_count=440,
        documents=[{}] * 440,
        fixed_cached_candidates=9513,
        quotas=dict.fromkeys(m.core.old.GROUPS, 60),
    )
    done = dict(
        protocol_id="prior",
        documents=440,
        input_candidates=9513,
        candidate_counts=dict(m.EXPECTED_PRIOR_COUNTS),
        status="FINANCIAL_ENUMERATION_COMPLETE_NOT_EVALUATION_READY",
    )
    geometry = dict(id="geometry", derived_geometry_view=True)
    complete = dict(
        protocol_id="geometry",
        documents=440,
        selected_pages=7530,
        coverage_pages=104439,
        original_blank_pages_rendered=420,
        status="GEOMETRY_COMPLETE_NOT_ADMITTED",
    )
    return parent, done, geometry, complete


def test_same_fixed_complete_population_allowed_without_mutating_previous():
    values = parents()
    before = copy.deepcopy(values)
    m.validate_fixed_scope(*values)
    assert values == before


@pytest.mark.parametrize(
    "index,key,value",
    [
        (0, "document_count", 439),
        (0, "quotas", dict.fromkeys(m.core.old.GROUPS, 40)),
        (1, "input_candidates", 9512),
        (1, "candidate_counts", dict(m.EXPECTED_PRIOR_COUNTS, dual_sufficient=60)),
        (2, "derived_geometry_view", False),
        (3, "coverage_pages", 104438),
        (3, "original_blank_pages_rendered", 419),
        (3, "status", "GEOMETRY_INCOMPLETE_NO_AUTOMATIC_RETRY"),
    ],
)
def test_changed_population_quota_or_incomplete_parent_rejected(index, key, value):
    values = parents()
    values[index][key] = value
    with pytest.raises(ValueError):
        m.validate_fixed_scope(*values)


def test_isolated_runner_preserves_financial_core_and_old_roots():
    old_root = m.core.RAW
    ns = m.execution_namespace()
    assert m.core.RAW == old_root and ns["RAW"] == m.RAW and m.RAW != m.PREVIOUS
    for name in (
        "financial_facts",
        "_fact",
        "document_qualify",
        "run",
        "year_columns",
        "unit_certificate",
    ):
        assert ns[name].__code__ is getattr(m.core, name).__code__
    assert ns["protocol"] is m.protocol
    assert ns["label_rows"].__code__ is not m.core.label_rows.__code__


def test_revision_writes_cannot_touch_previous_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "RAW", tmp_path / "new")
    old = tmp_path / "prior" / "summary.json"
    m.base.write(old, {"prior": True})
    with pytest.raises(ValueError, match="output_root"):
        m.save(old, {"prior": False})
    assert m.base.read(old) == {"prior": True}
