"""Explicit parent manifests and separate public/offline catalog capabilities."""

import hashlib
import json
from pathlib import Path

from ..finance_qa_vnext_task_build.archive import record, require, sha, validate_record, write_json

FAMILY_TO_SCALE = {
    "stock_rollforward": "stock_rollforward",
    "annual_flow": "annual_flow_components",
    "company_defined_metric": "defined_metric_reconstruction",
    "control": "control",
}
IDENTITY_FIELDS = (
    "task_id",
    "family",
    "surface_version_id",
    "public_messages_sha256",
    "parent_manifest_id",
)


def read(path):
    return json.loads(Path(path).read_bytes())


def safe_path(root, relative):
    relative = Path(relative)
    require(
        not relative.is_absolute() and ".." not in relative.parts, "catalog.relative_contained_path"
    )
    path = root / relative
    for current in (path, *path.parents):
        if current == root:
            break
        require(not current.is_symlink(), "catalog.no_symlink_members_or_parents")
    require(path.resolve().is_relative_to(root), "catalog.path_containment")
    return path


class Parent:
    def __init__(self, root, relative, expected_manifest_id=None):
        self.root = Path(root).resolve()
        self.relative = str(relative)
        self.directory = safe_path(self.root, relative)
        require(self.directory.is_relative_to(self.root), "catalog.parent_containment")
        manifest_path = safe_path(self.directory, "manifest.json")
        raw = manifest_path.read_bytes()
        self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        self.manifest = json.loads(raw)
        validate_record(self.manifest, "manifest")
        if expected_manifest_id:
            require(self.manifest["id"] == expected_manifest_id, "catalog.parent_manifest_pin")
        self.members = {row["path"]: row for row in self.manifest["members"]}
        require(len(self.members) == len(self.manifest["members"]), "catalog.unique_parent_members")

    def bytes(self, relative):
        self.check_manifest()
        require(relative in self.members, "catalog.member_declared")
        path = safe_path(self.directory, relative)
        require(
            path.is_relative_to(self.directory) and not path.is_symlink(),
            "catalog.member_containment",
        )
        content = path.read_bytes()
        item = self.members[relative]
        require(
            len(content) == item["bytes"] and hashlib.sha256(content).hexdigest() == item["sha256"],
            "catalog.parent_member_bytes",
        )
        return content

    def read(self, relative):
        return json.loads(self.bytes(relative))

    def check_manifest(self):
        require(
            sha(safe_path(self.directory, "manifest.json")) == self.manifest_sha256,
            "catalog.parent_manifest_bytes_unchanged",
        )

    def verify_all(self):
        for relative in self.members:
            self.bytes(relative)
        return self.manifest["id"]

    def descriptor(self):
        self.check_manifest()
        return {
            "directory": self.relative,
            "manifest_id": self.manifest["id"],
            "manifest_sha256": self.manifest_sha256,
        }


def compose(root, output, parents, frozen_id):
    root, output = Path(root).resolve(), Path(output)
    entries, seen = [], set()
    for parent in parents:
        catalog = parent.read("catalog.json")
        validate_record(catalog, "fixed_task_catalog")
        for row in catalog["tasks"]:
            bundle = parent.read(row["path"])
            validate_record(bundle, "TaskBundle")
            require(
                bundle["task_id"] == row["task_id"] and bundle["id"] == row["bundle_id"],
                "catalog.real_bundle_parent",
            )
            require(row["task_id"] not in seen, "catalog.no_duplicate_scientific_task")
            seen.add(row["task_id"])
            surface = bundle["surface_realization"]
            public_relative = str(Path(row["path"]).parent / "teacher_visible.json")
            public_bytes = parent.bytes(public_relative)
            digest = hashlib.sha256(public_bytes).hexdigest()
            require(digest == surface["public_messages_sha256"], "catalog.original_surface_bytes")
            require(bundle["family"] in FAMILY_TO_SCALE, "catalog.explicit_family_mapping")
            entries.append(
                {
                    "task_id": row["task_id"],
                    "family": bundle["family"],
                    "scale_group": FAMILY_TO_SCALE[bundle["family"]],
                    "surface_version_id": surface["surface_version_id"],
                    "public_messages_sha256": digest,
                    "parent_manifest_id": parent.manifest["id"],
                    "public_path": str(Path(parent.relative) / public_relative),
                    "bundle_path": str(Path(parent.relative) / row["path"]),
                    "native_bindings_path": str(Path(parent.relative) / "native_bindings.json"),
                    "parent_directory": parent.relative,
                    "bundle_id": bundle["id"],
                    "source_cluster": bundle["source_cluster"],
                    "quantity": bundle["private"]["canonical_target"]["quantity"],
                    "surface_category": surface["category"],
                }
            )
    require(len(entries) <= 260, "catalog.total_candidate_cap")
    full = record(
        "composed_task_catalog",
        stage_freeze_id=frozen_id,
        tasks=entries,
        parents=[parent.descriptor() for parent in parents],
        family_to_scale=FAMILY_TO_SCALE,
        preserved_parent_builds=True,
        enumeration="original parent catalog order, then new increment catalog order",
        final_training_population_selected=False,
        shared_AB_public_bytes=True,
    )
    public = record(
        "public_task_catalog",
        source_catalog_id=full["id"],
        tasks=[{key: item[key] for key in (*IDENTITY_FIELDS, "public_path")} for item in entries],
        contains_private_bundles=False,
    )
    write_json(output / "catalog.json", full)
    write_json(output / "public_catalog.json", public)
    return full, public


class PublicCatalog:
    """The online-facing reader never opens TaskBundle or native-binding files."""

    def __init__(self, root, index_path, expected_id):
        self.root = Path(root).resolve()
        index = read(safe_path(self.root, index_path))
        validate_record(index, "public_task_catalog")
        require(index["id"] == expected_id, "catalog.public_index_pin")
        self.tasks = {row["task_id"]: row for row in index["tasks"]}
        require(len(self.tasks) == len(index["tasks"]), "catalog.unique_public_tasks")
        for row in self.tasks.values():
            require(set(row) == {*IDENTITY_FIELDS, "public_path"}, "catalog.public_index_whitelist")

    def public_envelope(self, task_id):
        item = self.tasks[task_id]
        path = safe_path(self.root, item["public_path"])
        require(
            path.is_relative_to(self.root) and not path.is_symlink(),
            "catalog.public_file_containment",
        )
        raw = path.read_bytes()
        require(
            hashlib.sha256(raw).hexdigest() == item["public_messages_sha256"],
            "catalog.public_file_identity",
        )
        return {
            "identity": {key: item[key] for key in IDENTITY_FIELDS},
            "messages": json.loads(raw),
        }


class OfflineCatalog:
    """Private validation is a separate object, not passed to the worker."""

    def __init__(self, root, index_path, expected_id):
        self.root = Path(root).resolve()
        value = read(safe_path(self.root, index_path))
        validate_record(value, "composed_task_catalog")
        require(value["id"] == expected_id, "catalog.offline_index_pin")
        self.parents = {
            row["manifest_id"]: Parent(self.root, row["directory"], row["manifest_id"])
            for row in value["parents"]
        }
        self.tasks = {row["task_id"]: row for row in value["tasks"]}
        require(len(self.parents) == len(value["parents"]), "catalog.unique_offline_parents")
        require(len(self.tasks) == len(value["tasks"]), "catalog.unique_offline_tasks")
        require(
            len({row["directory"] for row in value["parents"]}) == len(value["parents"]),
            "catalog.unique_parent_directories",
        )
        self._bindings = {}

    def fixture(self, task_id, public_catalog):
        entry = self.tasks[task_id]
        parent = self.parents[entry["parent_manifest_id"]]
        relative = str(Path(entry["bundle_path"]).relative_to(parent.relative))
        bundle = parent.read(relative)
        require(
            bundle["id"] == entry["bundle_id"] and bundle["task_id"] == task_id,
            "catalog.offline_bundle_pin",
        )
        envelope = public_catalog.public_envelope(task_id)
        require(
            envelope["identity"] == {key: entry[key] for key in IDENTITY_FIELDS},
            "catalog.public_offline_surface_identity",
        )
        if parent.manifest["id"] not in self._bindings:
            self._bindings[parent.manifest["id"]] = parent.read("native_bindings.json")
        return {
            "bundle": bundle,
            "native_bindings": self._bindings[parent.manifest["id"]],
            **envelope,
        }
