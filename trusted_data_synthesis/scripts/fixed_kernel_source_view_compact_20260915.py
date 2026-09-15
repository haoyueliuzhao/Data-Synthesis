"""Lossless shared metadata layout over the already admitted 180 source views.

No new record selection, source read, private witness inspection, or prompt search
occurs. Expanding every compact view must exactly recover its admitted v1 public
object. Only repeated document/concept metadata are stored once instead of per row.
"""

# ruff: noqa: E501 -- frozen provenance strings and explicit artifact paths

import argparse
import copy
import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_source_view_runtime_20260915 as prior

p = prior.p
BASE = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/given_sources_value_20260915"
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_source_view_compact_20260915.py"
DOCUMENT_FIELDS = {"raw_object_id", "raw_sha256", "original_url", "source_kind"}
CONCEPT_FIELDS = {"label", "definition"}
SYSTEM = prior.SYSTEM


def compact_public(public):
    document, concepts, rows = None, {}, []
    for source in public["sources"]:
        common = {key: source[key] for key in DOCUMENT_FIELDS}
        p.require(document in (None, common), "compact.one_original_document_per_task")
        document = common
        definition = {key: source[key] for key in CONCEPT_FIELDS}
        p.require(
            source["concept"] not in concepts or concepts[source["concept"]] == definition,
            "compact.same_concept_metadata",
        )
        concepts[source["concept"]] = definition
        rows.append(
            {
                key: copy.deepcopy(value)
                for key, value in source.items()
                if key not in DOCUMENT_FIELDS | CONCEPT_FIELDS
            }
        )
    return {
        **copy.deepcopy(public),
        "sources": rows,
        "source_metadata": {"document": document, "concepts": concepts},
    }


def expand_public(public):
    metadata = public["source_metadata"]
    result = {
        key: copy.deepcopy(value) for key, value in public.items() if key != "source_metadata"
    }
    result["sources"] = [
        {
            **copy.deepcopy(row),
            **copy.deepcopy(metadata["document"]),
            **copy.deepcopy(metadata["concepts"][row["concept"]]),
        }
        for row in public["sources"]
    ]
    return result


class SourceViewSources:
    def __init__(self, public):
        self.public = copy.deepcopy(public)
        self.expanded = prior.SourceViewSources(expand_public(public))
        self.references = self.expanded.references

    def descriptors(self):
        return copy.deepcopy(self.public["sources"])

    def read_source(self, arguments):
        return self.expanded.read_source(arguments)


def binding():
    return p.record(
        "compact_source_view_runtime_binding",
        version="lossless_metadata_pool.v2:20260915",
        source_sha256=p.sha(Path(__file__)),
        expanded_runtime_binding=prior.binding(),
        SYSTEM_sha256=p.sha(SYSTEM),
        system_words_unchanged=True,
        expansion_is_exact_original_public_object=True,
        raw_records_pointers_and_source_IDs_unchanged=True,
        online_and_replay_same_runtime=True,
    )


def build_runtime():
    registered = binding()
    public_document = prior.isolation.clone_function(
        prior.public_document,
        {**vars(prior), "PUBLIC_FIELDS": prior.PUBLIC_FIELDS | {"source_metadata"}},
    )

    def record(kind, **fields):
        if kind == "evaluation_session":
            fields.update(
                source_view_runtime_binding_id=registered["id"],
                utility_environment="J_sources_not_J_snapshot",
                starts_without_Probe_history=True,
            )
        return prior.runtime.record(kind, **fields)

    namespace = {
        **vars(prior.runtime),
        "SYSTEM": SYSTEM,
        "public_document": public_document,
        "execute": prior.execute,
        "record": record,
    }
    generate = prior.isolation.clone_function(prior.runtime.generate, namespace)
    offline = {**vars(prior.assessment), "generate": generate}
    replay = prior.isolation.clone_function(prior.assessment.replay_session, offline)
    offline["replay_session"] = replay
    assess = prior.isolation.clone_function(prior.assessment.assess_session, offline)
    return SimpleNamespace(
        generate=generate,
        replay_session=replay,
        assess_session=assess,
        Sources=SourceViewSources,
        SYSTEM=SYSTEM,
        binding=registered,
    )


def prepare(root):
    from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
        load_tokenizer,
    )

    root = Path(root).resolve()
    before, output = root / BASE / "inputs", root / BASE / "inputs_v2"
    p.require(not output.exists(), "compact.unique_layout_no_reexecution")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    p.require(
        (root / SCRIPT).read_bytes()
        == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "compact.layout_committed_before_new_input",
    )
    manifest = p.checked(p.read_json(before / "manifest.json"), "source_view_manifest")
    admission = p.checked(p.read_json(before / "admission.json"), "source_view_input_admission")
    p.require(
        admission["passed"] and admission["manifest_id"] == manifest["id"],
        "compact.prior180_admission",
    )
    rule = p.record(
        "source_view_lossless_layout_rule",
        parent_source_rule_id=manifest["rule_id"],
        document_fields=sorted(DOCUMENT_FIELDS),
        concept_fields=sorted(CONCEPT_FIELDS),
        record_order_and_numeric_payload_unchanged=True,
        exact_roundtrip_required=True,
        system_prompt_unchanged=True,
        compiler_source_sha256=p.sha(Path(__file__)),
        rationale="six initial v1 inputs had less than4096 history headroom; minimum153; no Student outputs inspected",
    )
    p.write_once(output / "rule.json", rule)
    frozen = p.read_json(
        root
        / "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/parallel_tail_execution_20260914/preparation/execution_freeze.json"
    )
    tokenizer = load_tokenizer(frozen["tokenizer_binding"])
    started, rows, checks = time.monotonic(), [], []
    old_checks = {row["task_id"]: row for row in admission["checks"]}
    for row in manifest["tasks"]:
        old = p.read_json(root / row["path"])
        original = json.loads(old["public_messages"][0]["content"])
        visible = compact_public(original)
        p.require(expand_public(visible) == original, "compact.exact_lossless_public_roundtrip")
        messages = [{"role": "user", "content": p.encode(visible).decode()}]
        view = p.record(
            "given_public_source_view_v2",
            canonical_task_id=row["task_id"],
            group=row["group"],
            source_cluster=row["source_cluster"],
            original_identity=old["original_identity"],
            public_messages=messages,
            public_messages_sha256=p.sha(p.encode(messages)),
            parent_view_id=old["id"],
            rule_id=rule["id"],
            source_window=old["source_window"],
            original_source_document_id=old["source_document_id"],
            exact_lossless_expansion=True,
        )
        path = output / "views" / (row["task_id"] + ".json")
        p.write_once(path, view)
        rendered = tokenizer.apply_chat_template(
            [{"role": "system", "content": SYSTEM + "\nRequested guidance: neutral"}, *messages],
            tokenize=False,
            add_generation_prompt=True,
        )
        count = len(tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"])
        check = {
            **old_checks[row["task_id"]],
            "initial_prompt_tokens": count,
            "available_history_growth_tokens": 24576 - 2048 - count,
            "exact_lossless_expansion": True,
            "v1_initial_prompt_tokens": old_checks[row["task_id"]]["initial_prompt_tokens"],
        }
        check["passed"] = (
            old_checks[row["task_id"]]["passed"]
            and check["available_history_growth_tokens"] >= 4096
        )
        checks.append(check)
        rows.append(
            {
                **row,
                "path": str(path.relative_to(root)),
                "surface_version_id": view["id"],
                "public_messages_sha256": view["public_messages_sha256"],
            }
        )
    new_manifest = p.record(
        "source_view_manifest_v2",
        parent_manifest_id=manifest["id"],
        parent_admission_id=admission["id"],
        rule_id=rule["id"],
        tasks=rows,
        task_count=180,
        numeric_records_added_or_removed=0,
        new_raw_snapshot_reads=0,
        new_private_bundle_reads=0,
        code_commit=head,
    )
    p.write_once(output / "manifest.json", new_manifest)
    report = p.record(
        "source_view_input_admission_v2",
        status="PASS_ALL180_LOSSLESS_INPUTS"
        if all(row["passed"] for row in checks)
        else "BLOCKED_INPUT_CONTRACT",
        passed=all(row["passed"] for row in checks),
        manifest_id=new_manifest["id"],
        checks=checks,
        passed_tasks=sum(row["passed"] for row in checks),
        initial_prompt_tokens_min=min(row["initial_prompt_tokens"] for row in checks),
        initial_prompt_tokens_max=max(row["initial_prompt_tokens"] for row in checks),
        minimum_history_growth_tokens=min(row["available_history_growth_tokens"] for row in checks),
        runtime_binding=binding(),
        tokenizer_constructions=1,
        tokenizations=180,
        new_source_reads=0,
        new_private_bundle_reads=0,
        repeated_train_checks=0,
        model_calls=0,
        elapsed_seconds=time.monotonic() - started,
        finished_at=p.now(),
    )
    p.write_once(output / "admission.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    result = prepare(parser.parse_args().root)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "id",
                    "status",
                    "passed_tasks",
                    "initial_prompt_tokens_max",
                    "minimum_history_growth_tokens",
                )
            }
        )
    )
