"""Frozen B confirmation routing over unchanged public compilation and scoring.

Registry inspection reads metadata only. Public bodies are acquired only by
prepare_views after checking the committed code and persisted scientific freeze.
Private confirmation bundles are acquired only after the complete six-model
generation seal. No legacy dev admission or private support certificate is used
to admit a public confirmation view.
"""

import copy
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import fixed_kernel_given_sources_execution_20260915 as given
import fixed_kernel_source_view_compact_20260915 as views
import fixed_kernel_source_view_compile_20260915 as compiler

p = views.p
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_B_confirm_views_20260922.py"
REGISTRY = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/"
    "parallel_tail_execution_20260914/preparation/execution_freeze.json"
)
FIELDS = ("task_id", "group", "source_cluster", "surface_version_id", "public_messages_sha256")
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
SEEDS = (11, 29, 47)
CONDITIONS = ("static", "delayed_c")
CODE_PATHS = (
    SCRIPT,
    compiler.SCRIPT,
    compiler.RUNTIME_SCRIPT,
    views.SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_given_sources_execution_20260915.py",
)


def _path(root, value):
    candidate = Path(value)
    p.require(".." not in candidate.parts, "B_confirm.no_parent_path_escape")
    return candidate if candidate.is_absolute() else Path(root) / candidate


def registry(root, path=REGISTRY):
    """Return exactly the five original public registry identity fields, in order."""
    frozen = p.checked(p.read_json(_path(root, path)), "execution_freeze")
    rows = frozen["evaluation_registry"]["confirm"]
    p.require(
        len(rows) == 720
        and len({row["task_id"] for row in rows}) == 720
        and Counter(row["group"] for row in rows) == dict.fromkeys(GROUPS, 240)
        and all(set(row) == set(FIELDS) for row in rows)
        and all(re.fullmatch(r"cik:\d{10}", row["source_cluster"]) for row in rows),
        "B_confirm.original720_three_fixed240_groups",
    )
    dev = frozen["evaluation_registry"]["dev"]
    p.require(
        not {row["task_id"] for row in rows}.intersection(row["task_id"] for row in dev)
        and not {row["source_cluster"] for row in rows}.intersection(
            row["source_cluster"] for row in dev
        ),
        "B_confirm.dev_disjoint_task_and_CIK_registry",
    )
    return [{key: copy.deepcopy(row[key]) for key in FIELDS} for row in rows]


def _check_protocol(root, protocol, *, code=True):
    p.checked(protocol, "B_confirm_protocol")
    p.require(
        protocol.get("frozen") is True
        and protocol.get("candidate") == "Delayed-C"
        and protocol.get("baseline") == "Static"
        and protocol.get("split") == "confirm"
        and protocol.get("confirm_tasks") == 720
        and protocol.get("tasks_per_group") == 240
        and protocol.get("seeds") == list(SEEDS)
        and protocol.get("models_count") == 6
        and protocol.get("all_generation_before_private_scoring") is True,
        "B_confirm.frozen_unique_candidate_before_public_contents",
    )
    config = protocol["confirm_views"]
    p.require(
        p.read_json(_path(root, config["protocol_path"])) == protocol,
        "B_confirm.persisted_exact_scientific_freeze",
    )
    if code:
        sources = config["code_sources"]
        p.require(set(CODE_PATHS) <= set(sources), "B_confirm.complete_compiler_code_binding")
        for name, digest in sources.items():
            path = Path(name)
            p.require(
                not path.is_absolute() and ".." not in path.parts,
                "B_confirm.relative_committed_code_path",
            )
            committed = subprocess.check_output(
                ["git", "show", config["code_commit"] + ":" + name], cwd=root
            )
            p.require(
                p.sha(committed) == digest == p.sha(Path(root) / name),
                "B_confirm.code_committed_and_unchanged_before_public_contents",
            )
    rows = registry(root, config.get("registry_path", REGISTRY))
    p.require(
        p.sha(p.encode(rows)) == protocol["confirm_registry_sha256"],
        "B_confirm.original_registry_bytes_and_order",
    )
    return config, rows


def compile_view(public, document, row, original_identity, rule_id):
    """Pure public-only composition of the previously frozen v1 and v2 rules."""
    expanded, counts = compiler.compile_public(public, document, p)
    compact = views.compact_public(expanded)
    p.require(views.expand_public(compact) == expanded, "B_confirm.exact_v2_public_roundtrip")
    messages = [{"role": "user", "content": p.encode(compact).decode()}]
    view = p.record(
        "given_public_source_view_v2",
        canonical_task_id=row["task_id"],
        group=row["group"],
        source_cluster=row["source_cluster"],
        original_identity=original_identity,
        public_messages=messages,
        public_messages_sha256=p.sha(p.encode(messages)),
        rule_id=rule_id,
        source_window=counts,
        original_source_document_id=document["id"],
        exact_lossless_expansion=True,
        split="confirm",
        private_fields_received_by_compiler=False,
    )
    return view, expanded


def prepare_views(root, protocol):
    root = Path(root).resolve()
    config, rows = _check_protocol(root, protocol)
    output = _path(root, config["output_directory"])
    p.require(output.is_absolute() and not output.exists(), "B_confirm.new_exclusive_output")
    source_root = _path(root, config["source_root"])
    _, overlay, surface, Parent, safe_path, old_runtime, _ = compiler.modules(root)
    frozen = p.read_json(_path(root, config.get("registry_path", REGISTRY)))
    p.require(
        source_root.resolve() == Path(frozen["source_root"]).resolve(),
        "B_confirm.original_public_source_root",
    )
    # The freeze and all compiler byte checks above precede even the public catalog.
    public = overlay.PublicOverlay(source_root, surface.OUTPUT, given.original.SURFACE_MANIFEST_ID)
    science = Parent(source_root, surface.PARENT_PANEL, surface.PARENT_PANEL_MANIFEST)
    from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
        load_tokenizer,
    )

    tokenizer = load_tokenizer(frozen["tokenizer_binding"])
    rule = p.record(
        "B_confirm_public_view_rule",
        protocol_id=protocol["id"],
        source_rule=compiler.rule(p),
        compact_runtime_binding=views.binding(),
        code_commit=config["code_commit"],
        code_sources=config["code_sources"],
        minimum_history_growth_tokens=4096,
        private_support_admission_performed=False,
        model_calls=0,
    )
    p.write_once(output / "rule.json", rule)
    cache, documents, snapshots, compiled, checks, failures = {}, {}, {}, [], [], []
    public_document = views.prior.isolation.clone_function(
        views.prior.public_document,
        {**vars(views.prior), "PUBLIC_FIELDS": views.prior.PUBLIC_FIELDS | {"source_metadata"}},
    )
    for row in rows:
        task = row["task_id"]
        try:
            entry = public.tasks[task]
            p.require(
                entry["split"] == "confirm"
                and entry["family"] == row["group"]
                and entry["surface_version_id"] == row["surface_version_id"]
                and entry["public_messages_sha256"] == row["public_messages_sha256"],
                "B_confirm.public_original_registry_join",
            )
            messages = compiler.read_member(
                public.parent, entry["public_path"], p, safe_path, cache
            )
            p.require(
                p.sha(p.encode(messages)) == row["public_messages_sha256"],
                "B_confirm.original_public_bytes",
            )
            original = overlay.public_object(messages)
            p.require(
                original["period_contract"]["task_id"] == task
                and original["period_contract"]["source_cluster"] == row["source_cluster"],
                "B_confirm.original_task_and_CIK",
            )
            descriptor = original["source_document"]
            source_id = descriptor["source_id"]
            if source_id not in documents:
                document = compiler.read_member(
                    science, "panels/confirm/" + descriptor["path"], p, safe_path, cache
                )
                p.require(
                    document["id"] == descriptor["document_id"]
                    and document["complete_original_snapshot"]
                    == descriptor["complete_original_snapshot"],
                    "B_confirm.original_public_source_document",
                )
                documents[source_id] = document
                snapshots[source_id] = old_runtime.SnapshotSources(
                    source_root, [descriptor]
                )._payload(source_id)
            document = documents[source_id]
            p.require(
                document["id"] == descriptor["document_id"]
                and document["complete_original_snapshot"]
                == descriptor["complete_original_snapshot"],
                "B_confirm.shared_document_descriptor_unchanged",
            )
            original_identity = dict(
                task_id=task,
                family=row["group"],
                surface_version_id=row["surface_version_id"],
                public_messages_sha256=row["public_messages_sha256"],
                parent_manifest_id=public.parent.manifest["id"],
            )
            view, expanded = compile_view(original, document, row, original_identity, rule["id"])
            for source in expanded["sources"]:
                p.require(
                    old_runtime._pointer(snapshots[source_id], source["native_pointer"])
                    == source["record"]
                    and source["raw_sha256"] == descriptor["complete_original_snapshot"]["sha256"],
                    "B_confirm.actual_original_public_record_bytes",
                )
            identity = {
                **original_identity,
                "surface_version_id": view["id"],
                "public_messages_sha256": view["public_messages_sha256"],
                "parent_manifest_id": rule["id"],
            }
            packed = json.loads(view["public_messages"][0]["content"])
            public_document(view["public_messages"], identity, views.SourceViewSources(packed))
            rendered = tokenizer.apply_chat_template(
                [
                    {"role": "system", "content": views.SYSTEM + "\nRequested guidance: neutral"},
                    *view["public_messages"],
                ],
                tokenize=False,
                add_generation_prompt=True,
            )
            count = len(
                tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"]
            )
            path = output / "views" / (task + ".json")
            p.write_once(path, view)
            compiled.append(
                {
                    **row,
                    "path": str(path),
                    "surface_version_id": view["id"],
                    "public_messages_sha256": view["public_messages_sha256"],
                    **view["source_window"],
                }
            )
            checks.append(
                dict(
                    task_id=task,
                    group=row["group"],
                    initial_prompt_tokens=count,
                    available_history_growth_tokens=24576 - 2048 - count,
                    passed=24576 - 2048 - count >= 4096,
                )
            )
        except (ValueError, TypeError, KeyError) as error:
            failures.append(dict(task_id=task, error=str(error)))
    manifest = p.record(
        "source_view_manifest_v2",
        protocol_id=protocol["id"],
        split="confirm",
        rule_id=rule["id"],
        original_registry_sha256=protocol["confirm_registry_sha256"],
        tasks=compiled,
        task_count=len(compiled),
        planned_tasks=720,
        tasks_per_group=240,
        failures=failures,
        source_documents_read=len(documents),
        raw_snapshots_read=len(snapshots),
        private_bundle_reads=0,
        private_support_admission_performed=False,
        runtime_binding=views.binding(),
        code_commit=config["code_commit"],
    )
    p.write_once(output / "manifest.json", manifest)
    admitted = not failures and len(checks) == 720 and all(row["passed"] for row in checks)
    admission = p.record(
        "B_confirm_public_input_admission",
        protocol_id=protocol["id"],
        manifest_id=manifest["id"],
        passed=admitted,
        status="PASS_ALL720_PUBLIC_INPUTS" if admitted else "BLOCKED_INPUT_CONTRACT",
        checks=checks,
        failures=failures,
        passed_tasks=sum(row["passed"] for row in checks),
        planned_tasks=720,
        tokenizer_constructions=1,
        private_bundle_reads=0,
        private_sufficiency_checked=False,
        model_calls=0,
        failed_inputs_not_dropped_or_repaired=True,
        finished_at=p.now(),
    )
    p.write_once(output / "admission.json", admission)
    return manifest, admission


def require_generation_seal(root, protocol, manifest, seal_path):
    """Validate all six complete 720-row manifests before any private read."""
    seal = p.checked(p.read_json(_path(root, seal_path)), "B_confirm_generation_seal")
    p.checked(manifest, "source_view_manifest_v2")
    p.require(
        seal.get("complete") is True
        and seal.get("all_generation_workers_exited") is True
        and seal["protocol_id"] == protocol["id"] == manifest["protocol_id"]
        and seal["source_manifest_id"] == manifest["id"]
        and seal["total_trajectories"] == 4320
        and manifest["split"] == "confirm"
        and len(manifest["tasks"]) == 720
        and len(seal["models"]) == 6
        and {(row["condition"], row["seed"]) for row in seal["models"]}
        == {(condition, seed) for condition in CONDITIONS for seed in SEEDS},
        "B_confirm.all_six_models_sealed_before_any_private_read",
    )
    task_ids = [row["task_id"] for row in manifest["tasks"]]
    p.require(len(set(task_ids)) == 720, "B_confirm.sealed_unique720_tasks")
    for model in seal["models"]:
        path = _path(root, model["generation_manifest_path"])
        raw = path.read_bytes()
        p.require(
            p.sha(raw) == model["generation_manifest_sha256"], "B_confirm.sealed_manifest_bytes"
        )
        generated = p.checked(json.loads(raw), "anchored_generation_manifest")
        trajectories = generated["trajectories"]
        p.require(
            generated["complete"] is True
            and generated["stochastic"] is False
            and generated["point_id"] == model["point_id"]
            and generated["source_manifest_id"] == manifest["id"]
            and generated["tasks"] == manifest["tasks"]
            and len(trajectories) == 720
            and [item["job"]["task"] for item in trajectories] == manifest["tasks"]
            and [item["job"]["index"] for item in trajectories] == list(range(720))
            and all(
                item["point_id"] == model["point_id"]
                and item["job"]["repeat"] == 0
                and item["private_assessment_performed"] is False
                for item in trajectories
            ),
            "B_confirm.six_complete_original_cohorts_no_partial_scoring",
        )
    return seal


def offline_assets(root, protocol, manifest, seal_path):
    """Open private confirm assets once, after the global generation barrier."""
    config, original_rows = _check_protocol(root, protocol)
    p.require(
        [
            {key: row[key] for key in ("task_id", "group", "source_cluster")}
            for row in manifest["tasks"]
        ]
        == [
            {key: row[key] for key in ("task_id", "group", "source_cluster")}
            for row in original_rows
        ],
        "B_confirm.exact_registered_scoring_cohort",
    )
    seal = require_generation_seal(root, protocol, manifest, seal_path)
    _, _, surface, Parent, safe_path, _, _ = compiler.modules(root)
    parent = Parent(
        _path(root, config["source_root"]), surface.PARENT_PANEL, surface.PARENT_PANEL_MANIFEST
    )
    cache = {}

    def read(member):
        return compiler.read_member(parent, member, p, safe_path, cache)

    catalog = read("panels/confirm/catalog.json")
    registered = {row["task_id"]: row for row in catalog["tasks"]}
    bindings = read("panels/confirm/native_bindings.json")
    bundles = {}
    for row in original_rows:
        entry = registered[row["task_id"]]
        bundle = read("panels/confirm/" + entry["path"])
        p.require(
            bundle["task_id"] == row["task_id"]
            and bundle["source_cluster"] == row["source_cluster"]
            and bundle["family"] == row["group"]
            and bundle["id"] == entry["bundle_id"],
            "B_confirm.original_private_bundle_metadata_join",
        )
        bundles[row["task_id"]] = bundle
    return dict(
        bundles=bundles,
        native_bindings=bindings,
        private_uses="offline_confirmation_scoring_after_all4320_sealed",
        confirm_bundles_opened=720,
        generation_seal_id=seal["id"],
        source_manifest_id=manifest["id"],
        sealed_point_ids=[row["point_id"] for row in seal["models"]],
    )


def initialize_scoring(root, private, manifest_id, point_id):
    """Process initializer for unchanged feedback.score_one; routes only data."""
    p.require(
        private["source_manifest_id"] == manifest_id
        and private["confirm_bundles_opened"] == len(private["bundles"]) == 720
        and private["generation_seal_id"].startswith("B_confirm_generation_seal:")
        and point_id in private["sealed_point_ids"],
        "B_confirm.only_globally_sealed_private_scoring_capability",
    )
    import fixed_kernel_anchored_feedback_20260916 as feedback

    feedback._SCORING = (
        Path(root),
        private,
        manifest_id,
        point_id,
        False,
        views.build_runtime(),
        {},
    )
