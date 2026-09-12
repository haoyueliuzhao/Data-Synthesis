"""Synthetic surface-only manifests; no original study/model/tokenizer execution."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_qa_vnext_readiness_revision_reassessment import typed_fixture

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.stage import seal
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import (
    assessment,
    controls,
    periods,
    runtime,
)
from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import overlay
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    record,
    sha,
    write_json,
)


def _identity(kind, value):
    return record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )


@pytest.fixture
def study(tmp_path, monkeypatch):
    # The production module fixes 900; this tiny filesystem fixture exercises
    # exactly the same index/manifest logic with one synthetic task per panel.
    monkeypatch.setattr(
        overlay,
        "QUOTAS",
        {"dev": {"composition_required": 1}, "confirm": {"composition_required": 1}},
    )
    directory = tmp_path / "science"
    originals = {}
    for index, split in enumerate(("dev", "confirm"), start=1):
        fixture = typed_fixture()
        cluster = "cik:" + str(index).zfill(10)
        payload = copy.deepcopy(fixture["sources"].payloads["snapshot"])
        payload["cik"] = index
        raw_path = tmp_path / "synthetic" / (split + ".json")
        write_json(raw_path, payload)
        public = fixture["bundle"]["public"]
        public["quantity_contract"].update(
            currency="USD", decimal_places=2, rounding="half away from zero", period_required=False
        )
        public["source_document"]["complete_original_snapshot"].update(
            path=str(raw_path.relative_to(tmp_path)),
            sha256=sha(raw_path),
            bytes=raw_path.stat().st_size,
        )
        for native in fixture["native_bindings"].values():
            native.update(source_cluster=cluster, raw_sha256=sha(raw_path))
        target = fixture["bundle"]["private"]["canonical_target"]
        target["source_cluster"] = cluster
        task = "task_" + hashlib.sha256(runtime.encode(target)).hexdigest()
        public["period_contract"].update(task_id=task, source_cluster=cluster)
        contract = public["period_contract"]
        contract["id"] = (
            "actual_period_contract:"
            + hashlib.sha256(
                runtime.encode({key: value for key, value in contract.items() if key != "id"})
            ).hexdigest()
        )
        base = "What is the arithmetic mean of Revenue across these three annual observations?"
        public["question"] = base + "\n\n" + periods.render_public_periods(contract)
        messages = [
            {"role": "user", "content": json.dumps(public, ensure_ascii=False, sort_keys=True)}
        ]
        fixture["bundle"].update(task_id=task, source_cluster=cluster)
        fixture["bundle"]["private"]["private_canary"] = "NEVER_SEND_PRIVATE_EXPECTED_AMOUNT"
        fixture["bundle"]["parents"] = {
            "qa_id": "original-QA:" + split,
            "qa_build_id": "original-QA-Build:" + split,
        }
        fixture["bundle"]["validation"] = {
            "status": "passed",
            "meaning": "original deterministic QA template only",
        }
        fixture["bundle"]["surface"] = record(
            "evaluation_surface_version",
            task_id=task,
            public_messages_sha256=runtime.sha(runtime.encode(messages)),
        )
        bundle = _identity("EvaluationTaskBundle", fixture["bundle"])
        output = directory / "panels" / split
        bundle_path = f"tasks/{task}/task_bundle.json"
        public_path = f"tasks/{task}/public_messages.json"
        write_json(output / bundle_path, bundle)
        write_json(output / public_path, messages)
        write_json(output / "native_bindings.json", fixture["native_bindings"])
        row = {
            "task_id": task,
            "family": "composition_required",
            "path": bundle_path,
            "bundle_id": bundle["id"],
            "public_path": public_path,
            "public_messages_sha256": sha(output / public_path),
            "surface_version_id": bundle["surface"]["id"],
            "qa_id": bundle["parents"]["qa_id"],
            "qa_build_id": bundle["parents"]["qa_build_id"],
        }
        write_json(
            output / "catalog.json",
            record("actual_period_evaluation_catalog", split=split, tasks=[row]),
        )
        originals[task] = json.loads((output / bundle_path).read_bytes())
    manifest = seal(directory, synthetic_only=True)
    return {"root": tmp_path, "directory": directory, "manifest": manifest, "originals": originals}


def entries(study):
    return overlay.load_entries(
        study["root"], study["directory"].relative_to(study["root"]), study["manifest"]["id"]
    )


def rendered(
    entry,
    text="Use all three listed annual observations to calculate the arithmetic mean of Revenue.",
):
    public = copy.deepcopy(overlay.public_object(entry["public_messages"]))
    _, suffix = overlay.split_question(public["question"])
    public["question"] = text + suffix
    messages = [{"role": "user", "content": json.dumps(public, ensure_ascii=False, sort_keys=True)}]
    return {
        "passed": True,
        "errors": [],
        "public": public,
        "messages": messages,
        "base_question": text,
        "public_messages_sha256": runtime.sha(runtime.encode(messages)),
        "validation": {"passed": True, "synthetic_guard_stub": True},
        "change_classification": {
            "category": overlay.ACCEPTED,
            "true_lexical_change": True,
            "final_base_changed_original": True,
            "local_preparation_counted_as_LLM_rewrite": False,
        },
    }


def evidence(category=overlay.ACCEPTED):
    return {
        "category": category,
        "requests": [{"request_id": "synthetic-request:1"}],
        "selected_variant_index": 0 if category != overlay.FALLBACK else None,
        "selected_candidate_applied_to_final": category == overlay.ACCEPTED,
        "canonical_preparation_changed_original": True,
    }


def write_all(study, *, category=overlay.ACCEPTED):
    originals = entries(study)
    output = study["root"] / "overlay"
    rows = [
        overlay.write_surface(
            study["root"],
            output,
            entry,
            rendered=rendered(entry),
            evidence=evidence(category),
            freeze_id="synthetic-overlay-freeze",
        )
        for entry in originals
    ]
    public, offline = overlay.write_catalog(
        study["root"], output, originals, rows, freeze_id="synthetic-overlay-freeze"
    )
    manifest = seal(output, synthetic_only=True)
    return output, originals, rows, public, offline, manifest


def test_production_quota_contract_is_the_same_900_not_two_surface_populations():
    assert overlay.QUOTAS == {
        "dev": dict.fromkeys(overlay.GROUPS, 60),
        "confirm": dict.fromkeys(overlay.GROUPS, 240),
    }
    assert sum(sum(groups.values()) for groups in overlay.QUOTAS.values()) == 900


def test_public_registry_load_never_reads_private_TaskBundle(study, monkeypatch):
    opened = []
    original = Path.read_bytes

    def read_only_public(path):
        opened.append(str(path))
        assert path.name != "task_bundle.json"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_only_public)
    rows = entries(study)
    assert len(rows) == 2
    assert all(set(row["identity"]) == runtime.IDENTITY_FIELDS for row in rows)
    assert all(row["identity"]["parent_manifest_id"] == study["manifest"]["id"] for row in rows)
    assert "NEVER_SEND_PRIVATE_EXPECTED_AMOUNT" not in json.dumps(rows)
    assert opened


@pytest.mark.parametrize("category", [overlay.FALLBACK, overlay.UNCHANGED])
def test_fallback_and_format_only_reuse_original_bytes_not_prepared_canonical(study, category):
    output, originals, rows, _, _, _ = write_all(study, category=category)
    for original in originals:
        # Compare by canonical ID rather than relying on catalog ordering.
        row = next(item for item in rows if item["task_id"] == original["task_id"])
        assert (output / row["public_path"]).read_bytes() == runtime.encode(
            original["public_messages"]
        )
        assert row["public_messages_sha256"] == original["original_public_sha256"]
        surface = json.loads((output / row["surface_path"]).read_bytes())
        assert surface["category"] == category
        assert not surface["selected_candidate_applied_to_final"]
        assert surface["canonical_preparation_changed_original"] is True
        assert not surface["qa_build_created"] and not surface["qa_sample_created"]


def test_new_runtime_manifest_identity_and_offline_dual_parent_chain(study):
    output, originals, rows, public_index, _, manifest = write_all(study)
    public = overlay.PublicOverlay(study["root"], output.relative_to(study["root"]), manifest["id"])
    offline = overlay.OfflineOverlay(
        study["root"], output.relative_to(study["root"]), manifest["id"]
    )
    assert public_index["task_count"] == public_index["scientific_task_count"] == 2
    assert set(public.tasks) == {row["task_id"] for row in originals}
    task = rows[0]["task_id"]
    envelope = public.public_envelope(task)
    assert set(envelope["identity"]) == runtime.IDENTITY_FIELDS
    assert envelope["identity"]["parent_manifest_id"] == manifest["id"] != study["manifest"]["id"]
    bundle = offline.runtime_bundle(task)
    old = study["originals"][task]
    assert bundle["task_id"] == old["task_id"] and bundle["id"] != old["id"]
    assert bundle["private"] == old["private"] and bundle["parents"] == old["parents"]
    assert bundle["public"] == json.loads(envelope["messages"][0]["content"])
    proof = bundle["surface_overlay_provenance"]
    assert proof["scientific_parent"]["manifest_id"] == study["manifest"]["id"]
    assert proof["public_surface_parent"]["manifest_id"] == manifest["id"]
    assert proof["original_QA_parents_sha256"] == runtime.sha(runtime.encode(old["parents"]))
    assert (
        not proof["new_QA_build_created"]
        and proof["rewritten_question_is_not_an_original_QA_sample"]
    )
    assert bundle["validation"]["scientific_validation"] == old["validation"]


def test_overlay_public_runtime_and_offline_assessment_join_without_private_leak(study):
    output, _, rows, _, _, manifest = write_all(study)
    offline = overlay.OfflineOverlay(
        study["root"], output.relative_to(study["root"]), manifest["id"]
    )
    fixture = offline.fixture(rows[0]["task_id"])
    script = [controls.read("Revenue", index) for index in range(3)]
    script += [
        controls.calculate("avg(a,b,c)", a="tool:1", b="tool:2", c="tool:3"),
        controls.final(200, "tool:4"),
    ]
    responses = iter(script)

    def provider(messages, context):
        assert "NEVER_SEND_PRIVATE_EXPECTED_AMOUNT" not in json.dumps([messages, context])
        return runtime.encode(next(responses)).decode()

    session = runtime.generate(
        fixture["messages"], fixture["identity"], fixture["sources"], provider=provider
    )
    result = assessment.assess_session(
        session, fixture["bundle"], fixture["native_bindings"], fixture["sources"]
    )
    assert result["financial_valid"] and result["complete_trajectory_qualified"], result
    assert result["actual_method"] == "temporal_component_integration"


def test_real_guard_rendered_contract_matches_surface_writer(study):
    from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import guard

    entry = entries(study)[0]
    public = overlay.public_object(entry["public_messages"])
    spec = guard.build_spec(public, entry["identity"])
    assert "NEVER_SEND_PRIVATE_EXPECTED_AMOUNT" not in json.dumps(spec["model_contract"])
    candidate = guard.render_and_validate(
        spec["canonical_template"].replace("Calculate", "Determine"), spec
    )
    assert (
        candidate["passed"] and candidate["change_classification"]["category"] == overlay.ACCEPTED
    )
    proof = evidence()
    proof["canonical_preparation_changed_original"] = spec["canonical_preparation_changed_original"]
    row = overlay.write_surface(
        study["root"],
        study["root"] / "overlay",
        entry,
        rendered=candidate,
        evidence=proof,
        freeze_id="guard-overlay-synthetic",
    )
    assert row["public_messages_sha256"] == candidate["public_messages_sha256"]


def test_format_only_guard_result_cannot_be_claimed_as_true_rewrite(study):
    from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import guard

    entry = entries(study)[0]
    spec = guard.build_spec(overlay.public_object(entry["public_messages"]), entry["identity"])
    candidate = guard.render_and_validate(spec["canonical_template"], spec)
    assert (
        candidate["passed"] and candidate["change_classification"]["category"] == overlay.UNCHANGED
    )
    with pytest.raises(ValueError, match="true_rewrite_classification_required"):
        overlay.write_surface(
            study["root"],
            study["root"] / "overlay",
            entry,
            rendered=candidate,
            evidence=evidence(),
            freeze_id="guard-overlay-synthetic",
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "period_operation",
        "source",
        "unit",
        "suffix",
        "unchanged_base",
        "hash",
        "guard_failure",
        "missing_receipt",
    ],
)
def test_overlay_rejects_any_nonwording_change_before_write(study, mutation):
    entry = entries(study)[0]
    candidate = rendered(entry)
    proof = evidence()
    if mutation == "period_operation":
        candidate["public"]["period_contract"]["operation"]["kind"] = "difference"
    elif mutation == "source":
        candidate["public"]["source_document"]["source_id"] = "other-source"
    elif mutation == "unit":
        candidate["public"]["quantity_contract"]["unit"] = "USD"
    elif mutation == "suffix":
        candidate["public"]["question"] += " changed"
    elif mutation == "unchanged_base":
        candidate["base_question"] = overlay.split_question(
            overlay.public_object(entry["public_messages"])["question"]
        )[0]
    elif mutation == "hash":
        candidate["public_messages_sha256"] = "0" * 64
    elif mutation == "guard_failure":
        candidate["passed"] = False
    else:
        proof["requests"] = []
    with pytest.raises(ValueError):
        overlay.write_surface(
            study["root"],
            study["root"] / "overlay",
            entry,
            rendered=candidate,
            evidence=proof,
            freeze_id="frozen",
        )
    assert not (study["root"] / "overlay").exists()


def test_no_duplicate_task_or_scientific_split_reassignment(study):
    original = entries(study)
    output = study["root"] / "overlay"
    rows = [
        overlay.write_surface(
            study["root"],
            output,
            entry,
            rendered=rendered(entry),
            evidence=evidence(),
            freeze_id="freeze",
        )
        for entry in original
    ]
    with pytest.raises(ValueError, match="same_scientific_task_set"):
        overlay.write_catalog(
            study["root"], output, original, [rows[0], rows[0]], freeze_id="freeze"
        )
    swapped = copy.deepcopy(rows)
    swapped[0]["split"], swapped[1]["split"] = swapped[1]["split"], swapped[0]["split"]
    with pytest.raises(ValueError, match="family_and_split_unchanged"):
        overlay.write_catalog(study["root"], output, original, swapped, freeze_id="freeze")


def test_public_overlay_access_does_not_open_offline_index_or_private_bundle(study, monkeypatch):
    output, _, rows, _, _, manifest = write_all(study)
    actual = Path.read_bytes

    def only_public(path):
        assert path.name not in {"task_bundle.json", overlay.OFFLINE_INDEX, "surface.json"}
        return actual(path)

    monkeypatch.setattr(Path, "read_bytes", only_public)
    public = overlay.PublicOverlay(study["root"], output.relative_to(study["root"]), manifest["id"])
    assert public.public_envelope(rows[0]["task_id"])["messages"]


def test_modified_sealed_public_or_science_bytes_are_not_silently_consumed(study):
    output, original, rows, _, _, manifest = write_all(study)
    public = overlay.PublicOverlay(study["root"], output.relative_to(study["root"]), manifest["id"])
    public_path = output / rows[0]["public_path"]
    before = public_path.read_bytes()
    public_path.write_bytes(before + b" ")
    with pytest.raises(ValueError, match="parent_member_bytes"):
        public.public_envelope(rows[0]["task_id"])
    public_path.write_bytes(before)
    offline = overlay.OfflineOverlay(
        study["root"], output.relative_to(study["root"]), manifest["id"]
    )
    ref = original[0]["original_bundle_reference"]
    path = study["root"] / ref["parent_directory"] / ref["bundle_member"]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="parent_member_bytes"):
        offline.runtime_bundle(original[0]["task_id"])
