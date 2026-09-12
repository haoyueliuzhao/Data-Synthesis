"""Post-freeze read-only supplement for explicit YoY questions with one public period.

Preserves the frozen auditor's first failure as FAIL. Does not change its code,
any TaskBundle, any rule of source admission, or any model response. The only
supplement is a public-calendar derivation: previous year-end = public current
period start minus one day, with an explicit year-over-year phrase and two
uniquely matching original annual totals. This is not a financial NL proof.
"""

import argparse
import hashlib
import importlib.util
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

PATH = Path(__file__).with_name("audit_qa_vnext_catalog_incremental.py")
SPEC = importlib.util.spec_from_file_location("frozen_incremental_source_audit", PATH)
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
require, read, canonical = base.require, base.read, base.canonical


class YoyAudit(base.IncrementalAudit):
    def public_target(self, public):
        try:
            return super().public_target(public)
        except ValueError as error:
            require(str(error) == "two explicit question endpoint dates", "only registered failure")
        require(public["quantity_contract"]["unit"] == "percent", "supplement only public percent")
        question = public["question"]
        require(re.search(r"\byear[- ]over[- ]year\b", question), "explicit public YoY phrase")
        scopes = re.findall(
            r"\bin the period (\d{4}-\d{2}-\d{2}) through (\d{4}-\d{2}-\d{2})\b", question
        )
        require(len(scopes) == 1, "one explicit public current annual period")
        start, current_end = scopes[0]
        require(
            set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", question)) == {start, current_end},
            "no other public dates in supplemented question",
        )
        previous_end = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
        require(
            330 <= (date.fromisoformat(current_end) - date.fromisoformat(previous_end)).days <= 380,
            "public current period annual adjacency",
        )
        endpoints = {}
        for source in public["sources"]:
            require(
                source.get("source_kind") == "original_issuer_reconciliation",
                "supplement original issuer sources only",
            )
            identifier = source["source_id"]
            for header in self.header_sets[identifier]:
                end = header["period_end"]
                if end not in {previous_end, current_end}:
                    continue
                value, _ = self.table_amount(identifier, self.selected_rows[identifier][-1], end)
                require(
                    end not in endpoints or endpoints[end] == value, "unique source annual total"
                )
                endpoints[end] = value
        require(
            set(endpoints) == {previous_end, current_end}, "both original yearly endpoints exist"
        )
        previous, current = endpoints[previous_end], endpoints[current_end]
        require(previous > 0, "positive original prior-year base")
        contract = public["quantity_contract"]
        require(
            contract["decimal_places"] == 2 and contract["rounding"] == "half away from zero",
            "unchanged public rounding",
        )
        self.supplemented.append(
            {
                "question": question,
                "public_current_start": start,
                "public_current_end": current_end,
                "derived_previous_end": previous_end,
                "calendar_rule": "public start minus one day",
                "previous_original_total": str(previous),
                "current_original_total": str(current),
                "private_dates_or_answer_used_to_choose_endpoints": False,
            }
        )
        return 100 * (current - previous) / previous


def save(path, value, sealed):
    path = Path(path).resolve()
    require(not path.is_relative_to(sealed), "sidecar outside sealed root")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def old_public_bytes(root, frozen, composed):
    descriptor = frozen["parent"]
    directory = root / descriptor["directory"]
    manifest_path = directory / "manifest.json"
    require(
        hashlib.sha256(manifest_path.read_bytes()).hexdigest() == descriptor["manifest_sha256"],
        "old manifest literal SHA",
    )
    manifest = read(manifest_path)
    base.check_identity(manifest)
    require(manifest["id"] == descriptor["manifest_id"], "old parent manifest identity")
    members = {row["path"]: row for row in manifest["members"]}

    def member(path):
        data = (directory / path).read_bytes()
        require(len(data) == members[path]["bytes"], "old member size")
        require(hashlib.sha256(data).hexdigest() == members[path]["sha256"], "old member SHA")
        return data

    catalog = json.loads(member("catalog.json"))
    base.check_identity(catalog)
    current = {row["task_id"]: row for row in composed["tasks"]}
    require(len(catalog["tasks"]) == 233, "fixed 233 old tasks")
    for item in catalog["tasks"]:
        bundle = json.loads(member(item["path"]))
        base.check_identity(bundle)
        visible_path = str(Path(item["path"]).parent / "teacher_visible.json")
        data = member(visible_path)
        digest = hashlib.sha256(data).hexdigest()
        require(
            digest == bundle["surface_realization"]["public_messages_sha256"],
            "old surface and public literal bytes",
        )
        require(
            json.loads(data) == [{"role": "user", "content": canonical(bundle["public"]).decode()}],
            "old exact public projection",
        )
        row = current[item["task_id"]]
        require(
            row["parent_manifest_id"] == manifest["id"]
            and row["bundle_id"] == bundle["id"]
            and row["public_messages_sha256"] == digest,
            "composed catalog retains old original parent and public bytes",
        )
    return {
        "old_public_tasks_verified": 233,
        "old_public_bytes_unchanged": True,
        "old_parent_manifest_id": manifest["id"],
        "old_financial_semantics_reaudited": False,
    }


def run(root, directory, first_output, supplement_output):
    root, directory = Path(root).resolve(), Path(directory)
    sealed = (root / directory).resolve().parent
    frozen = read(sealed / "stage_freeze.json")
    base.check_identity(frozen)
    pins = {row["path"]: row for row in frozen["code"]}
    for path in (PATH, base._PARENT):
        relative = str(path.resolve().relative_to(root))
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == pins[relative]["sha256"],
            "original frozen auditor code unchanged",
        )
    checker = base.IncrementalAudit(root, directory)
    manifest_id = checker.verify_manifest()
    checker.verify_sources()
    source_counts = dict(checker.counts)
    try:
        checker.verify_tasks()
    except ValueError as error:
        first_error = str(error)
    else:
        raise ValueError("first frozen audit failure no longer reproduced")
    diagnostics = []
    for item in read(checker.stage / "catalog.json")["tasks"]:
        bundle = read(checker.stage / item["path"])
        visible = (checker.stage / item["path"]).parent / "teacher_visible.json"
        row = {
            "task_id": item["task_id"],
            "question": bundle["public"]["question"],
            "public_messages_sha256": hashlib.sha256(visible.read_bytes()).hexdigest(),
            "question_utf8_sha256": hashlib.sha256(
                bundle["public"]["question"].encode()
            ).hexdigest(),
            "quantity": bundle["private"]["canonical_target"]["quantity"],
        }
        try:
            value = checker.public_target(bundle["public"])
            require(
                value == Decimal(bundle["private"]["answer_exact"]), "original public target match"
            )
            row.update(status="ORIGINAL_PUBLIC_TARGET_PASS", answer_exact=str(value))
        except ValueError as error:
            row.update(status="ORIGINAL_PUBLIC_TARGET_FAIL", reason=str(error))
        diagnostics.append(row)
    first = {
        "schema_version": "incremental_frozen_auditor_failure.v1",
        "status": "FAIL",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "first_error": first_error,
        "input_manifest_id": manifest_id,
        "stage_freeze_id": frozen["id"],
        "frozen_auditor_sha256": hashlib.sha256(PATH.read_bytes()).hexdigest(),
        "verified_source_counts_before_failure": source_counts,
        "original_public_target_passed": sum(
            row["status"].endswith("_PASS") for row in diagnostics
        ),
        "original_public_target_failed": sum(
            row["status"].endswith("_FAIL") for row in diagnostics
        ),
        "tasks": diagnostics,
        "production_artifacts_changed": False,
        "model_calls": 0,
        "limitation": (
            "frozen auditor requires two explicit year-end dates even for implicit prior-year "
            "YoY questions"
        ),
    }
    save(first_output, first, sealed)
    supplement = YoyAudit(root, directory)
    supplement.supplemented = []
    require(supplement.verify_manifest() == manifest_id, "same immutable increment")
    supplement.verify_sources()
    tasks = supplement.verify_tasks()
    composed = read(sealed / "catalog.json")
    base.check_identity(composed)
    report = {
        "schema_version": "incremental_yoy_read_only_supplement.v1",
        "status": "PASS_AS_READ_ONLY_SUPPLEMENT",
        "original_frozen_auditor_status": "FAIL",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_manifest_id": manifest_id,
        "stage_freeze_id": frozen["id"],
        "frozen_auditor_sha256": hashlib.sha256(PATH.read_bytes()).hexdigest(),
        "supplement_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "first_failure_sidecar": str(Path(first_output).resolve().relative_to(root)),
        "selection_rule": (
            "explicit public YoY + exact current annual period; previous end = start minus one day"
        ),
        "post_freeze_auditor_domain_extension": True,
        "new_source_admission_or_task_generation": False,
        "counts": dict(supplement.counts),
        "tasks": tasks,
        "supplemented_questions": supplement.supplemented,
        **old_public_bytes(root, frozen, composed),
        "production_artifacts_changed": False,
        "model_calls": 0,
        "financial_natural_language_equivalence_proven_by_this_supplement": False,
    }
    save(supplement_output, report, sealed)
    return {
        key: report[key]
        for key in (
            "status",
            "original_frozen_auditor_status",
            "counts",
            "old_public_tasks_verified",
            "old_public_bytes_unchanged",
        )
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--directory", type=Path, default=Path(base.STAGE))
    parser.add_argument("--first-output", type=Path, required=True)
    parser.add_argument("--supplement-output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.root, args.directory, args.first_output, args.supplement_output),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
