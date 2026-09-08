"""One zero-generation stage: finite objects, original packages and CPU tokens."""

import argparse
import subprocess
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view import audit as old_audit
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.runtime import Runtime
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.representation import (
    encode_original_candidate,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    tokenization as assets,
)

from .judgments import review_session
from .measurement import measure, mechanism_comparisons, package_index
from .projection import project
from .rules import (
    BASELINE,
    DOCUMENT,
    MAX_SEQUENCE_LENGTH,
    OUTPUT,
    PACKAGE,
    PARENT,
    TEST,
    VALID,
    rule,
)
from .source import candidate, load_session, population, read, sha, snapshot

TOKEN_PARENT = (
    "trusted_data_synthesis/artifacts/qa_vnext_harness_transfer/"
    "h1_h2_four_instance_v1_20260907/preparation"
)


@contextmanager
def zero_execution():
    with execution_guard(online=False) as counts, ExitStack() as stack:

        def stop(name):
            counts[name] = 0

            def blocked(*args, **kwargs):
                counts[name] += 1
                raise RuntimeError("finqa_quotient.forbidden." + name)

            return blocked

        for owner, method, name in (
            (Runtime, "__init__", "numeric_runtime_construction"),
            (Runtime, "transition", "numeric_runtime_transition"),
            (old_audit, "verify_session", "old_session_reaudit"),
        ):
            stack.enter_context(patch.object(owner, method, stop(name)))
        yield counts


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def source_freeze(root):
    allowed = (PACKAGE + "/", OUTPUT + "/")
    exact = {DOCUMENT, TEST}
    changed = git(
        root, "diff", "--name-only", BASELINE, "--", "trusted_data_synthesis"
    ).splitlines()
    require(all(p in exact or p.startswith(allowed) for p in changed), "stage.history_unchanged")
    require(not git(root, "diff", "HEAD", "--", PACKAGE, TEST), "stage.source_committed")
    files = sorted((root / PACKAGE).glob("*.py")) + [root / TEST]
    members = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        require(git(root, "ls-files", "--", relative) == relative, "stage.no_uncommitted_source")
        data = path.read_bytes()
        members.append({"path": relative, "bytes": len(data), "sha256": sha(data)})
    return record(
        "finqa_numeric_implementation",
        commit=git(root, "rev-parse", "HEAD"),
        tree=git(root, "rev-parse", "HEAD^{tree}"),
        history_baseline=BASELINE,
        historical_tracked_files_unchanged=True,
        members=members,
        dependency_authority="Git tree plus baseline noninterference; member list is "
        "new implementation/test files, not a complete runtime dependency closure",
    )


def representation_policy(binding, original):
    require(
        original["maximum_sequence_length"] == MAX_SEQUENCE_LENGTH, "tokens.existing_length_policy"
    )
    require(original["tokenizer_binding_id"] == binding["id"], "tokens.source_policy_binding")
    return record(
        "finqa_numeric_representation_policy",
        tokenizer_binding_id=binding["id"],
        historical_policy_id=original["id"],
        maximum_sequence_length=MAX_SEQUENCE_LENGTH,
        original_binding_length_field_unchanged=True,
        chat_suffix=assets.CHAT_SUFFIX,
        suffix_token_ids=assets.SUFFIX_TOKEN_IDS,
        mask_policy=assets.MASK_POLICY,
        input="actual HTTP messages including V1 view, feedback, and P protocol",
        target="original admitted model content, not Host view or normalized judgment",
        truncation=False,
        padding_side="right",
        causal_shift=1,
        group="complete successful trajectory, not one independently sampled row",
        gpu=False,
        student_weights=False,
        student_forward=False,
        training=False,
    )


def run(root):
    implementation = source_freeze(root)
    with zero_execution() as counts:
        parent_snapshot = snapshot(root / PARENT)
        original_population = population(root)
        store = DurableStore(root / OUTPUT)
        # These are written before any mapping/token results, within this single stage.
        store.json("freeze/implementation.json", implementation)
        store.json("freeze/rule.json", rule())
        store.write("freeze/design.md", (root / DOCUMENT).read_bytes())
        store.json("freeze/parent_snapshot.json", parent_snapshot)
        store.json("population.json", original_population)
        binding = read(root / TOKEN_PARENT / "tokenizer_binding.json")
        historical_policy = read(root / TOKEN_PARENT / "representation_policy.json")
        policy = representation_policy(binding, historical_policy)
        store.json("freeze/tokenizer_binding.json", binding)
        store.json("freeze/historical_representation_policy.json", historical_policy)
        store.json("freeze/representation_policy.json", policy)
        sessions, projections, all_candidates = {}, {}, {}
        by_label = {r["label"]: r for r in original_population["rows"]}
        for label in VALID:
            session = load_session(root, by_label[label])
            sessions[label] = session
            review = review_session(session)
            store.json(f"judgments/{label}.json", review)
            projection = project(session, review)
            projections[label] = projection
            store.json(f"projections/{label}.json", projection)
            rows = []
            for turn in session["turns"]:
                index = turn["binding"]["index"]
                store.json(f"raw/{label}/{index:03d}/binding.json", turn["binding"])
                for name, content in turn["contents"].items():
                    store.write(f"raw/{label}/{index:03d}/{name}.raw", content)
                if turn["event"]["admitted"]:
                    row = candidate(session, turn)
                    rows.append(row)
                    store.json(f"candidates/{label}/{index:03d}.json", row)
            all_candidates[label] = rows
        measurement = measure(original_population, projections)
        mechanisms = mechanism_comparisons(projections)
        store.json("measurement.json", measurement)
        store.json("mechanism_comparisons.json", mechanisms)
        tokenizer = assets.load_tokenizer(binding)
        packages, total_tokens, all_representations = [], 0, []
        for label in VALID:
            token_rows = []
            for row in all_candidates[label]:
                encoded = encode_original_candidate(
                    row, binding, tokenizer, maximum_sequence_length=MAX_SEQUENCE_LENGTH
                )
                encoded = record(
                    "finqa_numeric_token_representation",
                    **{k: v for k, v in encoded.items() if k not in {"id", "schema_version"}},
                    representation_policy_id=policy["id"],
                    view_condition=row["view_condition"],
                )
                store.json(f"tokens/{label}/{row['submission'] - 1:03d}.json", encoded)
                token_rows.append(encoded)
                all_representations.append(encoded)
                total_tokens += encoded["target_token_count"]
            assignment = next(a for a in measurement["assignments"] if a["label"] == label)
            package = package_index(sessions[label], all_candidates[label], token_rows, assignment)
            store.json(f"packages/{label}.json", package)
            packages.append(package)
        require(sum(len(s["turns"]) for s in sessions.values()) == 52, "stage.original_52")
        require(sum(len(rows) for rows in all_candidates.values()) == 49, "stage.original_49")
        require(snapshot(root / PARENT) == parent_snapshot, "stage.parent_bytes_unchanged")
        for member in implementation["members"]:
            require(
                sha((root / member["path"]).read_bytes()) == member["sha256"],
                "stage.frozen_code_unchanged",
            )
        guard = guard_report(
            counts, phase="existing_numerical_quotient_and_original_materialization"
        )
        store.json("execution_guards.json", guard)
        result = record(
            "finqa_numeric_materialization_report",
            rule_id=rule()["id"],
            source_commit=implementation["commit"],
            parent_snapshot_id=parent_snapshot["id"],
            population_id=original_population["id"],
            measurement_id=measurement["id"],
            registered=8,
            original_successes=3,
            original_failures=5,
            original_success_submissions=52,
            supervision_units=49,
            legal_reject_units=sum(
                r["disposition"] == "reject" for rows in all_candidates.values() for r in rows
            ),
            unadmitted_kept_out_of_targets=3,
            trajectory_packages=packages,
            tokenizer_policy_id=policy["id"],
            tokenizer_loaded=True,
            token_fit_rows=sum(r["consumable_token_representation"] for r in all_representations),
            token_not_fit_rows=sum(
                not r["consumable_token_representation"] for r in all_representations
            ),
            sequence_length_max=max(r["sequence_length"] for r in all_representations),
            target_token_count=total_tokens,
            cpu_token_representation_not_student_feasibility=True,
            new_provider_calls=0,
            new_qualifications=0,
            new_runtime_executions=0,
            student_loads=0,
            student_forwards=0,
            gpu_jobs=0,
            vtdo_updates=0,
            parent_all_files_unchanged=True,
            original_validity_rewritten=False,
            original_final_witnesses=[
                {
                    "label": label,
                    "validity_id": sessions[label]["audit"]["id"],
                    "final_expression": sessions[label]["audit"]["final_expression"],
                    "raw_final": sessions[label]["turns"][-1]["event"]["model_submission"],
                    "new_target_validation": False,
                }
                for label in VALID
            ],
            by_view=measurement["by_view"],
            mechanisms=mechanisms,
            fixed_two_task_effective_training_set=False,
            training_utility=None,
            novelty=None,
            contribution=None,
            original_49_rows_are_not_independent_trajectories=True,
        )
        store.json("report.json", result)
        seal_directory(store, kind="finqa_numeric_quotient_manifest", report_id=result["id"])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "verify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.mode == "verify":
        with zero_execution():
            result = manifest(args.root / OUTPUT)
        print(result["id"])
    else:
        result = run(args.root)
        print(
            {
                key: result[key]
                for key in (
                    "id",
                    "supervision_units",
                    "token_fit_rows",
                    "sequence_length_max",
                    "target_token_count",
                    "new_provider_calls",
                )
            }
        )


if __name__ == "__main__":
    main()
