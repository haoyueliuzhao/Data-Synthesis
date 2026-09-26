"""Stage05 execution contracts on synthetic metadata only; no real qualification."""

from copy import deepcopy
from pathlib import Path

import cross_market_unit_encoding_revision_20260927 as units
import pytest
import run_cross_market_unit_encoding_revision_05_20260927 as m


def replace_record(record, kind, **changes):
    body = {k: deepcopy(v) for k, v in record.items() if k not in {"id", "schema_version"}}
    body.update(changes)
    return m.base.record(kind, **body)


def scan_fixture():
    documents = [dict(document=dict(raw_object_id=f"synthetic-raw-{i}")) for i in range(440)]
    frozen_ref = dict(path="/tmp/synthetic-stage04/scan_summary.json", sha256="frozen", bytes=1)
    plan = dict(
        id="synthetic-stage05",
        parent_protocol_id="synthetic-stage04",
        documents=documents,
        parent_references=dict(frozen_anchor_scan=frozen_ref),
    )
    old_refs = [
        dict(
            path=f"/tmp/synthetic-stage04/anchors/{m.prior.key_for(d)}.json", sha256="old", bytes=1
        )
        for d in documents
    ]
    new_refs = [
        dict(path=str(m.RAW / "anchors" / (m.prior.key_for(d) + ".json")), sha256="new", bytes=1)
        for d in documents
    ]
    original = m.base.record(
        m.prior.SCAN_DONE,
        protocol_id=plan["parent_protocol_id"],
        documents=440,
        original_anchors=9513,
        added_anchors=20,
        total_anchors=9533,
        status="DIRECT_LABEL_ANCHORS_SCANNED_NOT_ADMITTED",
        results=old_refs,
    )
    scanned = m.base.record(
        m.prior.SCAN_DONE,
        protocol_id=plan["id"],
        documents=440,
        original_anchors=9513,
        added_anchors=20,
        total_anchors=9533,
        status="FROZEN_LITERAL_ANCHORS_REUSED_NO_NEW_SCAN",
        results=new_refs,
        source_scan_reference=frozen_ref,
        new_original_source_scans=0,
        explicit_cached_view=True,
    )
    return plan, scanned, original


def original_anchor_record(plan):
    return m.base.record(
        m.prior.SCAN,
        protocol_id=plan["parent_protocol_id"],
        status="LITERAL_ROW_SCAN_COMPLETE_NOT_FINANCIALLY_QUALIFIED",
        document=plan["documents"][0]["document"],
        new_anchors=[
            dict(
                candidate_id="source_geometry_anchor:synthetic",
                value=None,
                period_start=None,
                source_geometry_anchor_provenance=dict(geometry_id="g", row_word_indices=[1, 2, 3]),
            )
        ],
        mechanical_reviews=[
            dict(
                candidate_id="source_geometry_anchor:synthetic",
                mechanical_checks_passed=False,
                failures=["pending"],
            )
        ],
        skipped_existing=[],
        rejected_rows=[],
        counts=dict(new_row_anchors=1),
    )


def test_exact_anchor_content_and_pending_reviews_reused_without_mutating_original():
    plan, _, original_scan = scan_fixture()
    original = original_anchor_record(plan)
    before = deepcopy(original)
    source = original_scan["results"][0]
    derived = m.derived_anchor_record(plan, original, source)
    assert original == before
    assert derived["protocol_id"] == plan["id"] and derived["parent_scan_result"] == source
    assert derived["new_anchors"] == original["new_anchors"]
    assert derived["mechanical_reviews"] == original["mechanical_reviews"]
    assert derived["new_anchors"][0]["value"] is None
    assert derived["cache_view_not_rescan"]
    assert derived["id"] != original["id"]


def test_wrong_original_anchor_protocol_and_changed_record_identity_fail():
    plan, _, original_scan = scan_fixture()
    original = original_anchor_record(plan)
    wrong = replace_record(original, m.prior.SCAN, protocol_id="not-the-stage04-parent")
    with pytest.raises(ValueError, match="original_scan_parent"):
        m.derived_anchor_record(plan, wrong, original_scan["results"][0])
    original["new_anchors"][0]["value"] = "invented"
    with pytest.raises(ValueError, match="record_identity"):
        m.derived_anchor_record(plan, original, original_scan["results"][0])


def test_exact_twenty_anchor_scan_with_all_440_original_documents_is_accepted():
    plan, scanned, original = scan_fixture()
    before = deepcopy((plan, scanned, original))
    m.validate_reused_scan(plan, scanned, original)
    assert (plan, scanned, original) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("added_anchors", 21),
        ("original_anchors", 9512),
        ("total_anchors", 9534),
        ("documents", 439),
        ("new_original_source_scans", 1),
        ("explicit_cached_view", False),
        ("status", "DIRECT_LABEL_ANCHORS_SCANNED_NOT_ADMITTED"),
        ("source_scan_reference", dict(path="different", sha256="different", bytes=1)),
    ],
)
def test_valid_hash_does_not_authorize_changed_reuse_budget_or_identity(field, value):
    plan, scanned, original = scan_fixture()
    scanned = replace_record(scanned, m.prior.SCAN_DONE, **{field: value})
    with pytest.raises(ValueError, match="exact_reused_scan"):
        m.validate_reused_scan(plan, scanned, original)


@pytest.mark.parametrize(
    "mode", ["duplicate_old_doc", "duplicate_new_doc", "wrong_new_root", "missing_doc"]
)
def test_reused_document_membership_and_new_output_root_are_exact(mode):
    plan, scanned, original = scan_fixture()
    target = deepcopy(original if mode == "duplicate_old_doc" else scanned)
    refs = deepcopy(target["results"])
    if mode in {"duplicate_old_doc", "duplicate_new_doc"}:
        refs[-1] = deepcopy(refs[0])
    elif mode == "wrong_new_root":
        refs[0]["path"] = "/tmp/wrong-root/" + Path(refs[0]["path"]).name
    else:
        refs.pop()
    target = replace_record(target, m.prior.SCAN_DONE, results=refs)
    if mode == "duplicate_old_doc":
        original = target
    else:
        scanned = target
    with pytest.raises(ValueError, match="document_membership"):
        m.validate_reused_scan(plan, scanned, original)


def test_cached_view_same_parent_ref_cannot_hide_changed_anchor_content(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "RAW", tmp_path / "stage05")
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    plan, _, old_summary = scan_fixture()
    original = original_anchor_record(plan)
    first_ref = old_summary["results"][0]
    derived = m.derived_anchor_record(plan, original, first_ref)
    changed = deepcopy(derived["new_anchors"])
    changed[0]["candidate_id"] = "source_geometry_anchor:replacement"
    tampered = replace_record(derived, m.prior.SCAN, new_anchors=changed)
    m.base.write(m.RAW / "anchors" / (Path(first_ref["path"]).stem + ".json"), tampered)
    monkeypatch.setattr(m, "protocol", lambda _: plan)

    def read(reference):
        if reference == plan["parent_references"]["frozen_anchor_scan"]:
            return old_summary
        assert reference == first_ref
        return original

    monkeypatch.setattr(m.prior, "read_ref", read)
    with pytest.raises(ValueError, match="existing_anchor_view_exact_content"):
        m.reuse_anchors(tmp_path)


def test_unit_namespace_changes_only_unit_handler_and_preserves_old_globals():
    old_namespace = m.prior.namespace()
    old_handler = old_namespace["unit_certificate"]
    roots = (m.prior.RAW, m.prior.core.RAW)
    ns = m.financial_namespace()
    assert ns["unit_certificate"] is units.unit_certificate
    assert old_namespace["unit_certificate"] is old_handler
    assert (m.prior.RAW, m.prior.core.RAW) == roots
    for key in (
        "financial_facts",
        "_fact",
        "certify",
        "label_rows",
        "header_lines",
        "actual_ends",
        "year_columns",
        "locate_statement",
    ):
        assert ns[key].__code__ is old_namespace[key].__code__
    assert ns["old"].compile_candidates is old_namespace["old"].compile_candidates


def test_qualify_checks_exact_scan_before_dispatching_frozen_runner(monkeypatch, tmp_path):
    plan, scanned, original = scan_fixture()
    wrong = replace_record(scanned, m.prior.SCAN_DONE, added_anchors=21, total_anchors=9534)
    monkeypatch.setattr(m, "protocol", lambda _: plan)
    monkeypatch.setattr(m.base, "read", lambda _: wrong)
    monkeypatch.setattr(m.prior, "read_ref", lambda _: original)

    def forbidden(*args, **kwargs):
        raise AssertionError("qualification was dispatched too early")

    monkeypatch.setattr(m.adapter, "isolated_namespace", forbidden)
    with pytest.raises(ValueError, match="exact_reused_scan"):
        m.qualify(tmp_path)


def test_qualify_dispatches_isolated_new_root_and_exact_observation_cap(monkeypatch, tmp_path):
    plan, scanned, original = scan_fixture()
    monkeypatch.setattr(m, "protocol", lambda _: plan)
    monkeypatch.setattr(m.base, "read", lambda _: scanned)
    monkeypatch.setattr(m.prior, "read_ref", lambda _: original)
    real_factory = m.adapter.isolated_namespace
    captured = {}

    def capture(module, **overrides):
        ns = real_factory(module, **overrides)
        captured["namespace"] = ns
        ns["qualify"] = lambda _: "synthetic-dispatch-only"
        return ns

    monkeypatch.setattr(m.adapter, "isolated_namespace", capture)
    old_root = m.prior.RAW
    assert m.qualify(tmp_path) == "synthetic-dispatch-only"
    ns = captured["namespace"]
    assert ns["RAW"] == m.RAW != old_root and ns["MAX_OBSERVATIONS"] == 19066
    assert ns["protocol"] is m.protocol and ns["namespace"] is m.financial_namespace
    assert ns["save"].__globals__ is ns and ns["reserve"].__globals__ is ns
    assert m.prior.RAW == old_root and m.prior.MAX_OBSERVATIONS == 21074


def test_new_execution_root_cannot_overwrite_preserved_stage04(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "RAW", tmp_path / "new")
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    old = tmp_path / "prior/summary.json"
    m.base.write(old, dict(preserved=True))
    with pytest.raises(ValueError, match="output_root"):
        m.save(old, dict(preserved=False))
    assert m.base.read(old) == dict(preserved=True)


def test_isolated_new_cache_attempt_is_one_shot_and_does_not_reset_prior(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    ns = m.adapter.isolated_namespace(m.prior, RAW=tmp_path / "new")
    plan = dict(id="synthetic")
    ns["reserve"](plan, "document_attempts", "one")
    with pytest.raises(ValueError, match="unsettled_attempt"):
        ns["reserve"](plan, "document_attempts", "one")
    assert len(list((tmp_path / "new/document_attempts").glob("*.json"))) == 1
