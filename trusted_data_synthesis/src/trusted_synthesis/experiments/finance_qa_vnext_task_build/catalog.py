"""Explicit frozen synthesized-task reader; never defaults to FinQA or X1/X2."""

import json
from pathlib import Path

from .archive import OUTPUT, require, sha, validate_record
from .factory import teacher_messages


class SynthesizedTaskCatalog:
    def __init__(self, root, *, expected_manifest_id):
        self.directory = Path(root).resolve() / OUTPUT
        manifest = json.loads((self.directory / "manifest.json").read_bytes())
        validate_record(manifest, "manifest")
        require(manifest["id"] == expected_manifest_id, "catalog.explicit_manifest_pin")
        self.members = {row["path"]: row for row in manifest["members"]}
        catalog = self._read("catalog.json")
        validate_record(catalog, "fixed_task_catalog")
        self.tasks = {row["task_id"]: row for row in catalog["tasks"]}
        require(len(self.tasks) == len(catalog["tasks"]), "catalog.unique_semantic_targets")
        self.catalog_id = catalog["id"]

    def _read(self, relative):
        require(relative in self.members, "catalog.member_is_manifest_bound")
        path = self.directory / relative
        member = self.members[relative]
        require(
            path.stat().st_size == member["bytes"] and sha(path) == member["sha256"],
            "catalog.original_member_bytes",
        )
        return json.loads(path.read_bytes())

    def task_ids(self):
        return tuple(self.tasks)

    def public_messages(self, task_id):
        """The online-consumer API returns only the frozen public messages."""
        reference = self.tasks[task_id]
        bundle = self._read(reference["path"])
        validate_record(bundle, "TaskBundle")
        require(
            bundle["task_id"] == task_id and bundle["id"] == reference["bundle_id"],
            "catalog.bundle_parent",
        )
        require(bundle["validation"]["status"] == "passed", "catalog.validated_task_only")
        return teacher_messages(bundle)

    def private_oracle(self, task_id):
        """Explicit offline validation access; never appended to a model input."""
        return self._read(self.tasks[task_id]["path"])["private"]
