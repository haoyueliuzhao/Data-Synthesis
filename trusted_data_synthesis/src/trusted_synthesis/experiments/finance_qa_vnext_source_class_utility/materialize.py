"""Tokenize only twelve selected new original packages; reuse nine old arrays."""

from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)

from .plan import (
    CONTROL_LABELS,
    CONTROL_SOURCE,
    NE_SOURCE,
    OUTPUT,
    history_guard,
    read_json,
    record,
    reference,
    require,
    sha,
    training_config,
)
from .tokens import encode_candidate, load_bound_assets
from .weights import bound, build_view, validate_arrays


def materialize(root):
    root = Path(root)
    output = root / OUTPUT
    require(not (output / "materialization").exists(), "materialize.once_no_overwrite")
    derived = read_json(output / "quantity_revision/report.json")
    selection = read_json(output / "quantity_revision/support_selection.json")
    require(selection["status"] == "RAW_SUPPORT_ESTABLISHED", "materialize.raw_input_gate")
    with execution_guard(online=False) as counts:
        history_guard(root)
        store = DurableStore(output / "materialization")
        binding, policy, tokenizer = load_bound_assets(root)
        store.json("tokenizer_binding.json", binding)
        store.json("representation_policy.json", policy)
        old_view = read_json(root / CONTROL_SOURCE / "weight_view.json")
        old_packages = {p["session_label"]: p for p in old_view["packages"]}
        rows, packages, failures = [], [], []
        for label in CONTROL_LABELS:
            package = old_packages[label]
            bound(root, package["package_reference"])
            own = [r for r in old_view["rows"] if r["session_label"] == label]
            require(len(own) == 2, "materialize.old_control_original_two_rows")
            for row in own:
                token = bound(root, row["token_reference"])
                candidate = bound(root, row["candidate_reference"])
                raw = bound(root, row["target_raw_reference"], binary=True)
                validate_arrays(token, candidate, raw)
                rows.append(
                    {
                        k: row[k]
                        for k in (
                            "session_label",
                            "task_key",
                            "class_id",
                            "response_index",
                            "response_kind",
                            "target_token_count",
                            "sequence_length",
                            "token_reference",
                            "candidate_reference",
                            "target_raw_reference",
                        )
                    }
                )
            packages.append(
                {
                    "session_label": label,
                    "task_key": package["task_key"],
                    "route": "control",
                    "class_id": package["class_id"],
                    "source_package_id": package["package_id"],
                    "source_package_reference": package["package_reference"],
                    "source_closeout_id": package["source_closeout_id"],
                    "new_tokenization": False,
                    "existing_qualification_reused": True,
                }
            )
        derived_rows = {r["label"]: r for r in derived["rows"]}
        old_index = read_json(root / NE_SOURCE / "closeout/raw_packages/index.json")
        original_packages = {p["label"]: p for p in old_index["packages"]}
        new_counts, new_max_length = {}, 0
        for selected in selection["train"]:
            label, key = selected["label"], selected["task_key"]
            qualified = derived_rows[label]
            require(
                qualified["formula_driven_trace_verified"] and qualified["arm"] == "N",
                "materialize.new_qualification_not_old_parser_output",
            )
            if qualified["newly_eligible"]:
                prefixes = [
                    str(path.relative_to(root)).removesuffix(".candidate.json")
                    for path in sorted(
                        (output / f"quantity_revision/newly_eligible/positive/{label}").glob(
                            "*.candidate.json"
                        )
                    )
                ]
                package_ref = reference(root, OUTPUT + f"/quantity_revision/sessions/{label}.json")
                package_id = qualified["qualification_id"]
            else:
                original = original_packages[label]
                require(
                    original["class_id"] == qualified["class_id"],
                    "materialize.same_original_class_ID",
                )
                prefixes = [
                    NE_SOURCE + "/closeout/" + row["path_prefix"]
                    for row in original["positive_responses"]
                ]
                package_ref = reference(
                    root, NE_SOURCE + f"/closeout/raw_packages/packages/{label}.json"
                )
                package_id = original["id"]
            actual_result = read_json(root / NE_SOURCE / f"online/sessions/{label}/result.json")
            expected_indices = [
                e["response_index"]
                for e in actual_result["events"]
                if e["protocol_error"] is None
                and (e["tool_call"] is None or e["tool_call"]["output"]["status"] == "ok")
            ]
            observed_indices, token_counts = [], []
            for prefix in prefixes:
                candidate = read_json(root / (prefix + ".candidate.json"))
                raw = (root / (prefix + ".target.raw")).read_bytes()
                require(raw == candidate["target_response"].encode(), "materialize.raw_target")
                index = candidate["response_index"]
                event = actual_result["events"][index]
                original_request = read_json(
                    root
                    / NE_SOURCE
                    / f"online/sessions/{label}/turns/{index:03d}_http_request.body"
                )
                require(
                    candidate["input_messages"] == original_request["messages"]
                    and sha(raw) == event["raw_sha256"],
                    "materialize.actual_original_prefix",
                )
                token = encode_candidate(candidate, binding, policy, tokenizer)
                token_path = OUTPUT + f"/materialization/tokens/{label}/{index:03d}.json"
                store.json(f"tokens/{label}/{index:03d}.json", token)
                new_max_length = max(new_max_length, token["sequence_length"])
                observed_indices.append(index)
                if not token["consumable_token_representation"]:
                    failures.append(
                        {
                            "label": label,
                            "response_index": index,
                            "reason": token["reason"],
                            "sequence_length": token["sequence_length"],
                        }
                    )
                    continue
                validate_arrays(token, candidate, raw)
                token_counts.append(token["target_token_count"])
                rows.append(
                    {
                        "session_label": label,
                        "task_key": key,
                        "class_id": qualified["class_id"],
                        "response_index": index,
                        "response_kind": candidate["response_kind"],
                        "target_token_count": token["target_token_count"],
                        "sequence_length": token["sequence_length"],
                        "token_reference": reference(root, token_path),
                        "candidate_reference": reference(root, prefix + ".candidate.json"),
                        "target_raw_reference": reference(root, prefix + ".target.raw"),
                    }
                )
            require(
                observed_indices == expected_indices
                and actual_result["events"][observed_indices[-1]]["final"],
                "materialize.all_original_positive_turns_and_Final",
            )
            new_counts[label] = sum(token_counts)
            packages.append(
                {
                    "session_label": label,
                    "task_key": key,
                    "route": selected["route"],
                    "class_id": qualified["class_id"],
                    "source_package_id": package_id,
                    "source_package_reference": package_ref,
                    "source_closeout_id": qualified["qualification_id"],
                    "derived_qualification_reference": reference(
                        root, OUTPUT + f"/quantity_revision/sessions/{label}.json"
                    ),
                    "original_projection_id": qualified["projection"]["id"],
                    "new_tokenization": True,
                    "original_N_prefix_retained": True,
                }
            )
        require(len(new_counts) == 12, "materialize.twelve_new_only")
        view = None if failures else build_view(packages, rows)
        if view is not None:
            store.json("weight_view.json", view)
            store.json("training_configuration.json", training_config(view["totals"]))
        report = record(
            "original_materialization_report",
            status="INPUT_INADEQUATE" if failures else "INPUT_ESTABLISHED",
            selected_original_packages=21,
            newly_tokenized_packages=12,
            old_array_packages_reused=9,
            old_packages_retokenized=0,
            selected_new_target_token_counts=new_counts,
            new_maximum_sequence_length=new_max_length,
            source_selection_id=selection["id"],
            source_derivation_id=derived["id"],
            tokenizer_binding_id=binding["id"],
            representation_policy_id=policy["id"],
            view_id=view["id"] if view else None,
            actual_totals=view["totals"] if view else None,
            failures=failures,
            no_truncation_rewriting_or_replacement=True,
            old_control_view_reference=reference(root, CONTROL_SOURCE + "/weight_view.json"),
            heldout_original_packages=selection["heldout"],
            holdout_tokenization_training_greedy_and_NLL=0,
            Teacher_requests=0,
            Student_calls=0,
            Student_weights_loaded=False,
        )
        store.json("report.json", report)
        store.json(
            "execution_guards.json", guard_report(counts, phase="source_class_materialization")
        )
        seal_directory(store, kind="source_class_materialization_manifest", report_id=report["id"])
    return report
