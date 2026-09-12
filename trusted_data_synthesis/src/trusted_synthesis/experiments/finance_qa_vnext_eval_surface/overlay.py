"""Manifest-bound wording overlays over the same scientific evaluation tasks.

The rewrite registry uses the original scientific identity. After sealing, the
public runtime identity uses the *overlay* manifest, which actually contains its
new public bytes. Only the offline class reads an original TaskBundle/private
reference. No QA Build, source, task target, or answer is reconstructed here.
"""

import copy
import json
import re
from collections import Counter
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.catalog import Parent, safe_path
from ..finance_qa_vnext_eval_readiness.runtime import IDENTITY_FIELDS, SnapshotSources, encode
from ..finance_qa_vnext_eval_readiness.runtime import sha as bytes_sha
from ..finance_qa_vnext_task_build.archive import record, require, sha, validate_record, write_json

GROUPS = ("dual_sufficient", "composition_required", "other_financial")
QUOTAS = {"dev": dict.fromkeys(GROUPS, 60), "confirm": dict.fromkeys(GROUPS, 240)}
PUBLIC_FIELDS = {
    "question",
    "source_document",
    "quantity_contract",
    "source_policy",
    "tool_contract",
    "period_contract",
}
SEPARATOR = "\n\nActual comparison periods (inclusive source dates):"
PUBLIC_INDEX = "public_surface_catalog.json"
OFFLINE_INDEX = "offline_surface_catalog.json"
ACCEPTED = "accepted_true_rewrite"
UNCHANGED = "unchanged_or_format_only"
FALLBACK = "canonical_fallback"


def split_question(question):
    require(
        isinstance(question, str) and question.count(SEPARATOR) == 1,
        "overlay.exact_one_original_actual_period_suffix",
    )
    index = question.index(SEPARATOR)
    require(index > 0, "overlay.original_base_required")
    return question[:index], question[index:]


def public_object(messages):
    require(
        isinstance(messages, list)
        and len(messages) == 1
        and set(messages[0]) == {"role", "content"}
        and messages[0]["role"] == "user"
        and isinstance(messages[0]["content"], str),
        "overlay.single_original_user_message",
    )
    public = json.loads(messages[0]["content"])
    require(
        isinstance(public, dict) and set(public) == PUBLIC_FIELDS, "overlay.public_field_allowlist"
    )
    split_question(public["question"])
    return public


def _counts(entries):
    require(all(row["split"] in QUOTAS for row in entries), "overlay.registered_split_only")
    return {
        split: dict(
            Counter(
                row["identity"]["family"] if "identity" in row else row["family"]
                for row in entries
                if row["split"] == split
            )
        )
        for split in QUOTAS
    }


def _identity_fields(identity):
    require(set(identity) == IDENTITY_FIELDS, "overlay.runtime_identity_exact_five_fields")
    require(
        re.fullmatch(r"task_[0-9a-f]{64}", identity["task_id"]) is not None,
        "overlay.original_canonical_task_path_identity",
    )


def load_entries(root, parent_directory, expected_manifest_id):
    """Read only old catalog/public members, never any private TaskBundle.

    Entries are local stage inputs. The Provider receives only the separately
    protected ``spec.model_contract``, not these offline parent-reference fields.
    """
    parent = Parent(root, parent_directory, expected_manifest_id)
    entries = []
    for split in QUOTAS:
        catalog = parent.read(f"panels/{split}/catalog.json")
        validate_record(catalog, "actual_period_evaluation_catalog")
        for row in catalog["tasks"]:
            member = f"panels/{split}/" + row["public_path"]
            raw = parent.bytes(member)
            messages = json.loads(raw)
            require(
                encode(messages) == raw and bytes_sha(raw) == row["public_messages_sha256"],
                "overlay.original_public_literal_bytes",
            )
            public = public_object(messages)
            require(
                public["period_contract"]["task_id"] == row["task_id"],
                "overlay.original_public_task_join",
            )
            identity = {
                key: row[key]
                for key in ("task_id", "family", "surface_version_id", "public_messages_sha256")
            }
            identity["parent_manifest_id"] = parent.manifest["id"]
            _identity_fields(identity)
            reference = {
                "parent_directory": parent.relative,
                "parent_manifest_id": parent.manifest["id"],
                "parent_manifest_sha256": parent.manifest_sha256,
                "bundle_member": f"panels/{split}/" + row["path"],
                "bundle_id": row["bundle_id"],
                "public_member": member,
                "original_surface_version_id": row["surface_version_id"],
                "original_public_messages_sha256": row["public_messages_sha256"],
                "qa_id": row["qa_id"],
                "qa_build_id": row["qa_build_id"],
            }
            require(
                reference["bundle_member"] in parent.members,
                "overlay.original_bundle_member_declared",
            )
            entries.append(
                {
                    "task_id": row["task_id"],
                    "split": split,
                    "identity": identity,
                    "public_messages": messages,
                    "original_public_path": str(Path(parent.relative) / member),
                    "original_public_sha256": row["public_messages_sha256"],
                    "original_bundle_reference": reference,
                }
            )
    require(
        len({row["task_id"] for row in entries}) == len(entries),
        "overlay.one_entry_per_scientific_task",
    )
    require(_counts(entries) == QUOTAS, "overlay.exact_original_900_selected_tasks")
    parent.check_manifest()
    return entries


def _original(root, entry, *, read_private=False):
    _identity_fields(entry["identity"])
    reference = entry["original_bundle_reference"]
    require(
        entry["split"] in QUOTAS
        and reference["public_member"].startswith(f"panels/{entry['split']}/")
        and reference["bundle_member"].startswith(f"panels/{entry['split']}/"),
        "overlay.original_split_reference_immutable",
    )
    parent = Parent(root, reference["parent_directory"], reference["parent_manifest_id"])
    require(
        parent.manifest_sha256 == reference["parent_manifest_sha256"]
        and entry["identity"]["parent_manifest_id"] == parent.manifest["id"],
        "overlay.original_scientific_manifest_authority",
    )
    raw = parent.bytes(reference["public_member"])
    messages = json.loads(raw)
    require(
        messages == entry["public_messages"]
        and encode(messages) == raw
        and bytes_sha(raw)
        == reference["original_public_messages_sha256"]
        == entry["identity"]["public_messages_sha256"]
        == entry["original_public_sha256"]
        and entry["task_id"] == entry["identity"]["task_id"],
        "overlay.original_entry_public_identity",
    )
    require(
        entry["identity"]["surface_version_id"] == reference["original_surface_version_id"]
        and str(Path(parent.relative) / reference["public_member"])
        == entry["original_public_path"],
        "overlay.original_version_and_public_path",
    )
    public = public_object(messages)
    require(
        public["period_contract"]["task_id"] == entry["task_id"],
        "overlay.original_period_task_identity",
    )
    if not read_private:
        return parent, public, None
    original = parent.read(reference["bundle_member"])
    validate_record(original, "EvaluationTaskBundle")
    require(
        original["id"] == reference["bundle_id"]
        and original["task_id"] == entry["task_id"]
        and original["family"] == entry["identity"]["family"]
        and original["public"] == public,
        "overlay.original_private_bundle_public_join",
    )
    require(
        original["parents"]["qa_id"] == reference["qa_id"]
        and original["parents"]["qa_build_id"] == reference["qa_build_id"],
        "overlay.original_QA_build_and_sample_parent",
    )
    return parent, public, original


def write_surface(root, output, entry, *, rendered=None, evidence, freeze_id):
    """Persist one guarded new wording or byte-identical original fallback.

    ``rendered`` is guard.render_and_validate's return object for accepted text.
    For fallback/format-only it is ignored: the original public messages
    are reused literally. No guard canonical template can replace this fallback.
    ``evidence`` retains the category, ordered request receipts and selected
    variant index, plus any root-stage transport/guard evidence references.
    """
    root = Path(root).resolve()
    output = Path(output)
    output = output if output.is_absolute() else root / output
    output = safe_path(root, output.relative_to(root))
    parent, original, _ = _original(root, entry)
    require(
        freeze_id
        and output != root
        and not output.is_relative_to(parent.directory)
        and not parent.directory.is_relative_to(output),
        "overlay.new_dedicated_output_only",
    )
    require(
        isinstance(evidence, dict)
        and evidence.get("category") in {ACCEPTED, FALLBACK, UNCHANGED}
        and isinstance(evidence.get("requests"), list),
        "overlay.realization_evidence_shape",
    )
    category = evidence["category"]
    old_base, suffix = split_question(original["question"])
    applied = category == ACCEPTED
    require(
        evidence.get("selected_candidate_applied_to_final", applied) is applied,
        "overlay.selected_candidate_application_matches_category",
    )
    if applied:
        require(
            isinstance(rendered, dict)
            and rendered.get("passed") is True
            and rendered.get("errors") == [],
            "overlay.guard_accepted_candidate_required",
        )
        classification = rendered.get("change_classification") or {}
        require(
            classification.get("category") == ACCEPTED
            and classification.get("true_lexical_change") is True
            and classification.get("final_base_changed_original") is True
            and classification.get("local_preparation_counted_as_LLM_rewrite") is False,
            "overlay.guard_true_rewrite_classification_required",
        )
        public, messages = rendered["public"], rendered["messages"]
        new_base = rendered["base_question"]
        require(
            isinstance(new_base, str)
            and new_base.strip()
            and new_base != old_base
            and SEPARATOR not in new_base,
            "overlay.accepted_means_changed_base_only",
        )
        require(
            public_object(messages) == public and public["question"] == new_base + suffix,
            "overlay.new_base_exact_original_suffix",
        )
        require(
            {key: value for key, value in public.items() if key != "question"}
            == {key: value for key, value in original.items() if key != "question"},
            "overlay.source_quantity_period_operation_tools_immutable",
        )
        require(
            bytes_sha(encode(messages)) == rendered["public_messages_sha256"],
            "overlay.rendered_public_literal_hash",
        )
        require(
            type(evidence.get("selected_variant_index")) is int
            and evidence["selected_variant_index"] >= 0
            and bool(evidence["requests"]),
            "overlay.accepted_request_and_variant_evidence",
        )
    else:
        public, messages, new_base = (
            copy.deepcopy(original),
            copy.deepcopy(entry["public_messages"]),
            old_base,
        )
        require(
            category != FALLBACK or evidence.get("selected_variant_index") is None,
            "overlay.fallback_has_no_selected_rewrite_variant",
        )
    raw = encode(messages)
    surface = record(
        "evaluation_llm_surface_version",
        task_id=entry["task_id"],
        split=entry["split"],
        family=entry["identity"]["family"],
        freeze_id=freeze_id,
        category=category,
        original_identity=copy.deepcopy(entry["identity"]),
        scientific_parent_manifest_id=parent.manifest["id"],
        original_bundle_reference=copy.deepcopy(entry["original_bundle_reference"]),
        original_base_sha256=bytes_sha(old_base.encode()),
        new_base_sha256=bytes_sha(new_base.encode()),
        immutable_suffix_sha256=bytes_sha(suffix.encode()),
        public_messages_sha256=bytes_sha(raw),
        selected_variant_index=evidence.get("selected_variant_index"),
        evidence=copy.deepcopy(evidence),
        selected_candidate_applied_to_final=applied,
        canonical_preparation_changed_original=evidence.get(
            "canonical_preparation_changed_original"
        ),
        guard_validation=copy.deepcopy(rendered.get("validation")) if applied else None,
        canonical_task_id_unchanged=True,
        qa_build_created=False,
        qa_sample_created=False,
        original_QA_question_remains_in_original_parent=True,
        original_QA_checks_not_reexecuted_for_new_wording=True,
        fallback_reuses_original_messages_bytes=not applied,
    )
    directory = output / "surfaces" / entry["split"] / entry["task_id"]
    public_path, surface_path = directory / "public_messages.json", directory / "surface.json"
    write_json(public_path, messages)
    write_json(surface_path, surface)
    require(public_path.read_bytes() == raw, "overlay.persisted_public_bytes")
    return {
        "task_id": entry["task_id"],
        "split": entry["split"],
        "family": entry["identity"]["family"],
        "surface_version_id": surface["id"],
        "public_messages_sha256": surface["public_messages_sha256"],
        "public_path": str(public_path.relative_to(output)),
        "surface_path": str(surface_path.relative_to(output)),
        "scientific_parent_manifest_id": parent.manifest["id"],
        "category": category,
        "original_bundle_reference": copy.deepcopy(entry["original_bundle_reference"]),
    }


def write_catalog(root, output, original_entries, surface_entries, *, freeze_id):
    root, output = Path(root).resolve(), Path(output)
    output = output if output.is_absolute() else root / output
    output = safe_path(root, output.relative_to(root))
    original = {row["task_id"]: row for row in original_entries}
    require(
        len(original) == len(original_entries) == len(surface_entries)
        and {row["task_id"] for row in surface_entries} == set(original),
        "overlay.complete_same_scientific_task_set",
    )
    require(
        _counts(original_entries) == _counts(surface_entries) == QUOTAS,
        "overlay.unchanged_180_720_group_quotas",
    )
    ordered = sorted(surface_entries, key=lambda row: (row["split"], row["task_id"]))
    for row in ordered:
        require(
            row["original_bundle_reference"]
            == original[row["task_id"]]["original_bundle_reference"],
            "overlay.no_scientific_parent_rebinding",
        )
        require(
            row["split"] == original[row["task_id"]]["split"]
            and row["family"] == original[row["task_id"]]["identity"]["family"],
            "overlay.original_task_family_and_split_unchanged",
        )
        surface = json.loads(safe_path(output, row["surface_path"]).read_bytes())
        validate_record(surface, "evaluation_llm_surface_version")
        require(
            surface["id"] == row["surface_version_id"]
            and surface["freeze_id"] == freeze_id
            and surface["task_id"] == row["task_id"]
            and surface["split"] == row["split"]
            and surface["family"] == row["family"]
            and surface["original_identity"] == original[row["task_id"]]["identity"]
            and sha(safe_path(output, row["public_path"])) == row["public_messages_sha256"],
            "overlay.all_written_versions_and_public_hashes",
        )
    public_rows = [
        {key: value for key, value in row.items() if key != "original_bundle_reference"}
        for row in ordered
    ]
    public = record(
        "evaluation_public_surface_catalog",
        freeze_id=freeze_id,
        tasks=public_rows,
        task_count=len(ordered),
        scientific_task_count=len(original),
        quotas=QUOTAS,
        original_task_set_sha256=bytes_sha(encode(sorted(original))),
        runtime_identity_parent="dynamically_bound_to_this_catalogs_sealed_overlay_manifest",
        scientific_parents=sorted({row["scientific_parent_manifest_id"] for row in ordered}),
        old_and_new_surfaces_not_counted_as_separate_tasks=True,
        qa_builds_created=0,
    )
    offline = record(
        "evaluation_offline_surface_catalog",
        freeze_id=freeze_id,
        public_catalog_id=public["id"],
        tasks=ordered,
        task_count=len(ordered),
        private_bundles_are_original_read_only_references=True,
        new_QA_build_created=False,
    )
    write_json(output / PUBLIC_INDEX, public)
    write_json(output / OFFLINE_INDEX, offline)
    return public, offline


class PublicOverlay:
    """A public capability: reads only catalog and exact saved user messages."""

    def __init__(self, root, directory, expected_manifest_id):
        self.parent = Parent(root, directory, expected_manifest_id)
        self.catalog = self.parent.read(PUBLIC_INDEX)
        validate_record(self.catalog, "evaluation_public_surface_catalog")
        self.tasks = {row["task_id"]: row for row in self.catalog["tasks"]}
        require(
            len(self.tasks)
            == len(self.catalog["tasks"])
            == self.catalog["task_count"]
            == self.catalog["scientific_task_count"],
            "overlay.public_catalog_unique_task_denominator",
        )
        require(
            _counts(self.catalog["tasks"]) == QUOTAS == self.catalog["quotas"],
            "overlay.public_catalog_fixed_quotas",
        )
        allowed = {
            "task_id",
            "split",
            "family",
            "surface_version_id",
            "public_messages_sha256",
            "public_path",
            "surface_path",
            "scientific_parent_manifest_id",
            "category",
        }
        require(
            all(set(row) == allowed for row in self.tasks.values()),
            "overlay.public_index_field_allowlist",
        )
        require(
            all(row["category"] in {ACCEPTED, UNCHANGED, FALLBACK} for row in self.tasks.values()),
            "overlay.public_known_realization_category",
        )

    def public_envelope(self, task_id):
        require(task_id in self.tasks, "overlay.selected_task_required")
        row = self.tasks[task_id]
        raw = self.parent.bytes(row["public_path"])
        messages = json.loads(raw)
        require(
            encode(messages) == raw and bytes_sha(raw) == row["public_messages_sha256"],
            "overlay.sealed_new_public_bytes",
        )
        public = public_object(messages)
        require(public["period_contract"]["task_id"] == task_id, "overlay.sealed_public_task_join")
        identity = {
            key: row[key]
            for key in ("task_id", "family", "surface_version_id", "public_messages_sha256")
        }
        identity["parent_manifest_id"] = self.parent.manifest["id"]
        _identity_fields(identity)
        return {"identity": identity, "messages": messages}


class OfflineOverlay:
    """Explicit offline construction of a new surface view over immutable science."""

    def __init__(self, root, directory, expected_manifest_id):
        self.root = Path(root).resolve()
        self.public = PublicOverlay(root, directory, expected_manifest_id)
        self.parent = self.public.parent
        self.catalog = self.parent.read(OFFLINE_INDEX)
        validate_record(self.catalog, "evaluation_offline_surface_catalog")
        require(
            self.catalog["public_catalog_id"] == self.public.catalog["id"],
            "overlay.offline_public_catalog_join",
        )
        self.tasks = {row["task_id"]: row for row in self.catalog["tasks"]}
        require(
            len(self.tasks) == len(self.catalog["tasks"]) == self.catalog["task_count"]
            and set(self.tasks) == set(self.public.tasks),
            "overlay.offline_exact_public_task_set",
        )

    def runtime_bundle(self, task_id):
        require(task_id in self.tasks, "overlay.offline_selected_task_required")
        row = self.tasks[task_id]
        require(
            {key: value for key, value in row.items() if key != "original_bundle_reference"}
            == self.public.tasks[task_id],
            "overlay.offline_entry_public_identity",
        )
        surface = self.parent.read(row["surface_path"])
        validate_record(surface, "evaluation_llm_surface_version")
        require(
            surface["id"] == row["surface_version_id"]
            and surface["category"] == row["category"]
            and surface["public_messages_sha256"] == row["public_messages_sha256"]
            and surface["original_bundle_reference"] == row["original_bundle_reference"],
            "overlay.surface_metadata_and_scientific_reference",
        )
        reference = row["original_bundle_reference"]
        science = Parent(self.root, reference["parent_directory"], reference["parent_manifest_id"])
        messages = science.read(reference["public_member"])
        source_entry = {
            "task_id": task_id,
            "split": row["split"],
            "identity": surface["original_identity"],
            "public_messages": messages,
            "original_public_path": str(Path(science.relative) / reference["public_member"]),
            "original_public_sha256": reference["original_public_messages_sha256"],
            "original_bundle_reference": reference,
        }
        science, original_public, original = _original(self.root, source_entry, read_private=True)
        envelope = self.public.public_envelope(task_id)
        public = public_object(envelope["messages"])
        require(
            {key: value for key, value in public.items() if key != "question"}
            == {key: value for key, value in original_public.items() if key != "question"}
            and split_question(public["question"])[1]
            == split_question(original_public["question"])[1],
            "overlay.offline_immutable_scientific_public_contract",
        )
        if row["category"] != ACCEPTED:
            require(
                envelope["messages"] == messages, "overlay.offline_nonrewrite_original_public_bytes"
            )
        body = {
            key: copy.deepcopy(value)
            for key, value in original.items()
            if key not in {"id", "schema_version"}
        }
        body.update(
            public=public,
            surface=surface,
            validation={
                "status": "surface_overlay_only",
                "scientific_validation": copy.deepcopy(original["validation"]),
                "new_QA_build_created": False,
                "original_QA_checks_not_reexecuted": True,
            },
            surface_overlay_provenance={
                "scientific_parent": science.descriptor(),
                "original_bundle_id": original["id"],
                "original_bundle_schema_version": original["schema_version"],
                "original_bundle_member": reference["bundle_member"],
                "original_private_sha256": bytes_sha(encode(original["private"])),
                "original_QA_parents_sha256": bytes_sha(encode(original["parents"])),
                "public_surface_parent": self.parent.descriptor(),
                "surface_version_id": surface["id"],
                "canonical_task_id_unchanged": True,
                "new_QA_build_created": False,
                "new_QA_sample_created": False,
                "rewritten_question_is_not_an_original_QA_sample": row["category"] == ACCEPTED,
            },
        )
        return record("evaluation_surface_runtime_bundle", **body)

    def fixture(self, task_id):
        bundle = self.runtime_bundle(task_id)
        envelope = self.public.public_envelope(task_id)
        reference = self.tasks[task_id]["original_bundle_reference"]
        original = Parent(self.root, reference["parent_directory"], reference["parent_manifest_id"])
        bindings = original.read(f"panels/{self.tasks[task_id]['split']}/native_bindings.json")
        return {
            "bundle": bundle,
            "messages": envelope["messages"],
            "identity": envelope["identity"],
            "native_bindings": bindings,
            "sources": SnapshotSources(self.root, [bundle["public"]["source_document"]]),
        }
