"""One zero-provider stage: frozen finite measurement plus exact materialization."""

import argparse
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    save,
    write,
)

from .materialize import export
from .measurement import measure
from .n3 import clarification
from .plan import (
    AUDIT_PATH,
    AUDIT_SHA256,
    DOCUMENT,
    OUTPUT,
    PACKAGE,
    SOURCE,
    TESTS,
    encode,
    history_guard,
    record,
    require,
    rules,
    sha,
)
from .projection import project_session
from .source import load_population
from .tokens import BINDING_PATH, PARENT_POLICY_PATH, load_bound_assets


def frozen_code(root):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    paths = [PACKAGE, DOCUMENT, *TESTS]
    require(
        not subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=root),
        "stage.code_must_be_committed",
    )
    require(
        subprocess.check_output(["git", "rev-parse", "refs/remotes/origin/main"], cwd=root)
        .decode()
        .strip()
        == head,
        "stage.rules_must_be_pushed_before_measurement",
    )
    files = (
        subprocess.check_output(["git", "ls-files", "--", *paths], cwd=root).decode().splitlines()
    )
    require(
        len(files) >= 13 and DOCUMENT in files and all(p in files for p in TESTS),
        "stage.complete_code_freeze",
    )
    members = [
        {"path": p, "bytes": len((root / p).read_bytes()), "sha256": sha((root / p).read_bytes())}
        for p in files
    ]
    return record(
        "rule_source_freeze",
        git_commit=head,
        members=members,
        before_new_comparison_results=True,
        existing_original_trajectories_previously_reviewed=True,
    )


def seal(directory):
    members = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            require(not path.is_symlink(), "stage.no_artifact_symlink")
            raw = path.read_bytes()
            members.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "bytes": len(raw),
                    "sha256": sha(raw),
                }
            )
    value = record("open_materialization_manifest", members=members)
    save(directory, "manifest.json", value)
    # This verifies the new schema directly; no inherited State/action identities.
    verify(directory)
    return value


def verify(directory):
    import json

    sealed = json.loads((directory / "manifest.json").read_bytes())
    require(
        sealed == record("open_materialization_manifest", members=sealed["members"]),
        "stage.manifest_identity",
    )
    members = {m["path"]: m for m in sealed["members"]}
    actual = {
        p.relative_to(directory).as_posix(): p
        for p in directory.rglob("*")
        if p.is_file() and p != directory / "manifest.json"
    }
    require(
        len(members) == len(sealed["members"]) and set(actual) == set(members),
        "stage.manifest_complete",
    )
    for name, path in actual.items():
        require(
            not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()),
            "stage.manifest_safe_member",
        )
        raw = path.read_bytes()
        require(
            len(raw) == members[name]["bytes"] and sha(raw) == members[name]["sha256"],
            "stage.manifest_bytes",
        )
    return sealed


def run(root):
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    before = history_guard(root)
    freeze = frozen_code(root)
    destination = root / OUTPUT
    require(not destination.exists(), "stage.no_overwrite_or_silent_rerun")
    audit = Path(AUDIT_PATH).read_bytes()
    require(sha(audit) == AUDIT_SHA256, "stage.exact_user_audit")
    with execution_guard(online=False) as counts:
        parent, parent_manifests, sessions, valid = load_population(root)
        binding, token_policy, tokenizer = load_bound_assets(root)
        save(destination, "rules.json", rules())
        save(destination, "source_freeze.json", freeze)
        write(destination, "audit_request.txt", audit)
        write(destination, "tokenizer_binding.original.json", (root / BINDING_PATH).read_bytes())
        write(
            destination,
            "representation_policy.original.json",
            (root / PARENT_POLICY_PATH).read_bytes(),
        )
        save(destination, "token_policy.json", token_policy)
        save(destination, "original_population.json", parent)
        save(destination, "N3_task_clarification.json", clarification(sessions))
        save(
            destination,
            "source_snapshot.json",
            record(
                "immutable_open_source_snapshot",
                source_root=SOURCE,
                parent_manifests=parent_manifests,
                history=before,
                interactions=[t["binding"] for s in sessions.values() for t in s["turns"]],
            ),
        )
        print(
            "Source bound: 24 original registrations; 10 T and 2 A valid sessions. "
            "No new Provider calls.",
            flush=True,
        )
        projections = [project_session(s) for _, s in sorted(valid.items())]
        for item in projections:
            save(destination, f"behavior/{item['session_label']}.json", item)
        measured = measure(projections, parent["rows"])
        save(destination, "measurement.json", measured)
        print(
            "Finite original-trajectory measurement complete; "
            "materializing exact histories/targets on CPU.",
            flush=True,
        )
        index = export(
            root,
            destination / "materialization",
            sessions,
            valid,
            projections,
            measured,
            binding,
            token_policy,
            tokenizer,
        )
        after_manifests = {name: manifest(root / SOURCE / name)["id"] for name in parent_manifests}
        require(after_manifests == parent_manifests, "stage.source_snapshot_unchanged")
        after = history_guard(root)
        require(after == before, "stage.historical_files_unchanged")
        guards = guard_report(counts, phase="open_finite_measurement_and_original_materialization")
        save(destination, "execution_guards.json", guards)
        source_associations = Counter(
            item["source_association_attribution"]
            for p in projections
            for item in p.get("source_mapping_ledger", [])
        )
        report = record(
            "open_materialization_report",
            started_at_utc=started_at,
            elapsed_seconds=time.perf_counter() - started,
            source_freeze_id=freeze["id"],
            rules_id=rules()["id"],
            measurement_id=measured["id"],
            materialization_index_id=index["id"],
            original_registered=24,
            original_validity_preserved={
                p: {
                    "registered": parent["by_condition"][p]["registered"],
                    "formula_driven_verified": parent["by_condition"][p]["formula_driven_verified"],
                }
                for p in ("T", "A")
            },
            behavior_projection_statuses={
                population: dict(
                    Counter(p["status"] for p in projections if p["population"] == population)
                )
                for population in ("T", "A")
            },
            source_association_counts=dict(source_associations),
            source_attribution_is_not_automatic_financial_certification=True,
            original_error_responses_preserved_and_not_positive_targets=True,
            by_population=index["by_population"],
            guards_id=guards["id"],
            provider_calls=0,
            new_model_tokens=0,
            new_provider_cost=0,
            no_credential_read=True,
            student_weight_loads=0,
            student_forward_calls=0,
            gpu_used=False,
            training_steps=0,
            vtdo_updates=0,
            original_history_unchanged=True,
            N3_original_outcomes_unchanged=True,
            N3_new_versions_prospectively_validated=False,
            training_distribution_implemented=False,
            scope=(
                "finite existing open-trajectory behavior measurement and exact original "
                "representation only"
            ),
        )
        save(destination, "report.json", report)
    sealed = seal(destination)
    print(
        encode(
            {
                "report_id": report["id"],
                "artifact_files": len(sealed["members"]),
                "by_population": report["by_population"],
            }
        ).decode(),
        flush=True,
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "verify"))
    args = parser.parse_args()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip())
    if args.mode == "run":
        run(root)
    else:
        sealed = verify(root / OUTPUT)
        print(
            encode(
                {"manifest_id": sealed["id"], "verified_members": len(sealed["members"])}
            ).decode()
        )


if __name__ == "__main__":
    main()
