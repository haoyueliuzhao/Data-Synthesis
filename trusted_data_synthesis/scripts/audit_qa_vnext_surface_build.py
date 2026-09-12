"""Post-run source/receipt audit; no generation, plan executor or model imports.

The original source auditor assumed every structurally parsed table had facts.
This wrapper also reads frozen raw references for tables rejected before fact
materialization, without inventing database parents or changing source admission.
Natural-language equivalence remains a separate finite-parser check.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from audit_qa_vnext_task_build import Audit as SourceAudit
from audit_qa_vnext_task_build import check_identity, read, require
from lxml import html

STAGE = "trusted_data_synthesis/artifacts/qa_vnext_surface_build/task_surface_20260912"
PARENT = "trusted_data_synthesis/artifacts/qa_vnext_task_build/task_factory_20260911"


class Audit(SourceAudit):
    def verify_sources(self):
        inventory = read(self.stage / "issuer_source_tables.json")
        originals = {
            row["raw_object"]["raw_object_id"]: row["raw_object"] for row in inventory["sources"]
        }
        frozen = {
            row["raw_object_id"]: row
            for row in read(self.stage / "stage_freeze.json")["original_sources"]
            if "raw_object_id" in row
        }
        extra = {row["raw_object_id"] for row in inventory["tables"]} - self.raw.keys()
        for identifier in sorted(extra):
            raw, reference = originals[identifier], frozen[identifier]
            require(
                raw["storage_uri"].removeprefix("/workspace/Data Synthesis/") == reference["path"],
                "unmaterialized table original reference",
            )
            path = self.root / reference["path"]
            require(path.resolve().is_relative_to(self.root), "original source contained")
            data = path.read_bytes()
            require(
                len(data) == reference["bytes"] == raw["content_size_bytes"],
                "unmaterialized original source size",
            )
            require(
                hashlib.sha256(data).hexdigest() == reference["sha256"] == raw["content_sha256"],
                "unmaterialized original source SHA",
            )
            self.dom[identifier] = html.fromstring(data)
        self.counts["unmaterialized_table_original_files_separately_checked"] = len(extra)
        # self.raw and the exported parent tables are deliberately NOT enlarged.
        super().verify_sources()

    def verify_rewrites(self):
        registry = read(self.stage / "canonical_task_registry.json")
        check_identity(registry)
        targets = {row["task_id"]: row["target"] for row in registry["tasks"]}
        catalog = read(self.stage / "catalog.json")
        ledger = read(self.stage / "rewrite_budget_ledger.json")
        fixed = read(self.stage / "stage_freeze.json")["rule"]
        requests = {row["request_id"]: row for row in ledger["reservations"]}
        require(len(requests) == len(ledger["reservations"]) <= 520, "unique bounded requests")
        require(
            set(row["task_id"] for row in requests.values()) <= targets.keys(),
            "only registered tasks requested",
        )
        require(
            max(Counter(row["task_id"] for row in requests.values()).values()) <= 2,
            "per-task cap unchanged",
        )
        forbidden_keys = {
            "answer_payload",
            "answer_value",
            "answer_exact",
            "source_fact_ids",
            "source_derived_ids",
            "basis_witnesses",
            "relation_certificate",
            "canonical_target",
            "input_bindings",
            "entity_ids",
            "metric_ids",
            "definition_ids",
        }

        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        prompt_tokens = completion_tokens = returned_variants = 0
        for identifier, row in requests.items():
            directory = self.stage / "rewrite_requests" / identifier
            request, raw, receipt = (
                read(directory / name)
                for name in ("request.json", "raw_response.json", "receipt.json")
            )
            check_identity(request)
            check_identity(receipt)
            require(
                request["request_id"] == raw["request_id"] == receipt["request_id"] == identifier,
                "request response receipt identity",
            )
            require(
                request["task_id"] == row["task_id"] and request["attempt"] == row["attempt"],
                "ledger target attempt",
            )
            body = request["body"]
            require(
                set(body)
                == {"model", "messages", "thinking", "response_format", "max_tokens", "stream"},
                "closed actual HTTP fields",
            )
            require(
                body["model"] == fixed["strict_model_request"]["model"]
                and body["thinking"] == {"type": "disabled"}
                and body["max_tokens"] == 1536
                and body["stream"] is False,
                "actual registered model and cap",
            )
            require(
                request["purpose"] == "question_rewrite"
                and request["lower_level_attempts"] == 1
                and request["automatic_model_discovery"] is False
                and request["fallback_models"] == [],
                "no Teacher or alternative model attempts",
            )
            user = json.loads(body["messages"][1]["content"])
            require(
                not forbidden_keys.intersection(keys(user)), "no private answer or route fields"
            )
            require(
                user["semantic_cues"]["temporal_quantity"]["quantity"]
                == targets[row["task_id"]]["quantity"],
                "prompt quantity is registered task, not private solution route",
            )
            question = user["protected_question"]
            require(
                not re.search(r"\d", re.sub(r"<slot_[a-z_]+>", "", question)),
                "no literal numeric answers in protected question",
            )
            require(
                hashlib.sha256(raw["body_utf8"].encode()).hexdigest()
                == raw["received_body_sha256"],
                "actual response bytes intact",
            )
            envelope = json.loads(raw["body_utf8"])
            require(
                raw["http_status"] == 200
                and row["http_success"] == 1
                and envelope["model"] == body["model"] == row["response_model"],
                "actual HTTP and exact model identity",
            )
            usage = envelope["usage"]
            require(
                usage["prompt_tokens"] == row["prompt_tokens"]
                and usage["completion_tokens"] == row["completion_tokens"]
                and row["charged_tokens"] == row["prompt_tokens"] + row["completion_tokens"]
                and row["state"] == "settled",
                "reported usage matches persistent debit",
            )
            prompt_tokens += row["prompt_tokens"]
            completion_tokens += row["completion_tokens"]
            variants = json.loads(envelope["choices"][0]["message"]["content"])["rewrites"]
            require(1 <= len(variants) <= 2, "bounded returned variants")
            returned_variants += len(variants)
            if row["attempt"] == 2:
                require(
                    user["repair_contract"]["previous_error_codes"], "explicit contract-only repair"
                )
        categories, checked = Counter(), 0
        examples = {}
        for item in sorted(catalog["tasks"], key=lambda row: row["task_id"]):
            bundle = read(self.stage / item["path"])
            surface = bundle["surface_realization"]
            check_identity(surface)
            require(
                bundle["canonical_task_id"] == bundle["task_id"] == surface["canonical_task_id"],
                "canonical identity not multiplied by wording",
            )
            visible_path = (self.stage / item["path"]).parent / "teacher_visible.json"
            require(
                hashlib.sha256(visible_path.read_bytes()).hexdigest()
                == surface["public_messages_sha256"],
                "one literal public version for all future conditions",
            )
            changed = re.findall(r"\w+", bundle["public"]["question"].casefold()) != re.findall(
                r"\w+", surface["canonical_question"].casefold()
            )
            if surface["category"] == "accepted_true_rewrite":
                require(
                    changed and surface["generation_method"] == "controlled_llm_protected_rewrite",
                    "true rewrite is actual changed text",
                )
            elif surface["category"] == "canonical_fallback":
                require(
                    bundle["public"]["question"] == surface["canonical_question"],
                    "canonical fallback retained",
                )
            categories[surface["category"]] += 1
            checked += len(surface["generation_validation"]["variant_checks"])
            examples.setdefault(
                surface["category"],
                {
                    "task_id": item["task_id"],
                    "canonical": surface["canonical_question"],
                    "final": bundle["public"]["question"],
                },
            )
        parent = read(self.root / PARENT / "catalog.json")
        old_ids = {row["task_id"] for row in parent["tasks"]}
        new_ids = {row["task_id"] for row in catalog["tasks"]}
        require(new_ids == targets.keys(), "all registered tasks retained")
        return {
            "actual_requests": len(requests),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_debit_tokens": prompt_tokens + completion_tokens,
            "existing_global_cap_unchanged": 1_000_000_000,
            "debit_must_be_counted_by_future_budget_consumers": True,
            "this_is_not_an_additional_global_allowance": True,
            "returned_variants": returned_variants,
            "evaluated_variants": checked,
            "variants_not_evaluated_after_first_valid_accept": returned_variants - checked,
            "categories": dict(categories),
            "old_task_ids_retained": len(old_ids & new_ids),
            "new_scientific_task_ids": len(new_ids - old_ids),
            "old_task_ids_absent": len(old_ids - new_ids),
            "examples_rule": "first canonical task ID per category, not preferred style",
            "examples": examples,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = Audit(args.root, STAGE)
    manifest = audit.verify_manifest()
    audit.verify_sources()
    tasks = audit.verify_tasks()
    rewrites = audit.verify_rewrites()
    report = {
        "schema_version": "post_run_surface_source_receipt_audit.v1",
        "status": "passed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_manifest_id": manifest,
        "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "base_auditor_sha256": hashlib.sha256(
            Path(__file__).with_name("audit_qa_vnext_task_build.py").read_bytes()
        ).hexdigest(),
        "scope": (
            "post-run independent source arithmetic and request/usage/public-byte reconciliation"
        ),
        "natural_language_equivalence_proof": False,
        "natural_language_check_separate": "frozen finite temporal parser on actual final questions",
        "actual_final_question_count": len(tasks),
        "production_artifacts_changed": False,
        "model_calls_by_this_audit": 0,
        "counts": dict(audit.counts),
        "rewrite_receipts": rewrites,
        "tasks": tasks,
    }
    output = args.output.resolve()
    require(not output.is_relative_to(audit.stage), "report outside sealed stage")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "tasks"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
