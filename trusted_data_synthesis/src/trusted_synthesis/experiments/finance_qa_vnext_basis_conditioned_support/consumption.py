"""Representation gate over the caller's already sealed sixteen-package selection.

This pure entry point writes no files and cannot certify when a selection was
sealed. The caller must seal its audit and selection before calling, and supply
all positive candidate/raw pairs from source.candidates for each selected label.
Financial eligibility, actual method, complete classes, and completeness of the
source binding remain the upstream audit's authority. No training view is built.
"""

from . import tokens
from .plan import GENERATION_CONDITIONS, LABELS, METHODS, TASKS, encode, record, require, sha
from .tokens import load_bound_assets


def _selection(selection):
    require(isinstance(selection, dict), "consumption.selection_shape")
    require(
        selection
        == record(
            "basis_fixed_support_selection",
            **{k: v for k, v in selection.items() if k not in {"id", "schema_version"}},
        ),
        "consumption.selection_identity",
    )
    eligible = selection.get("eligible")
    require(isinstance(eligible, dict) and set(eligible) == set(TASKS), "consumption.exact_tasks")
    labels_seen = set()
    for task in TASKS:
        groups = eligible[task]
        require(
            isinstance(groups, dict) and set(groups) == set(METHODS), "consumption.exact_methods"
        )
        for method in METHODS:
            labels = groups[method]
            require(isinstance(labels, list), "consumption.eligible_list")
            require(
                all(isinstance(label, str) and label in LABELS for label in labels)
                and all(label.split("_")[1] == task for label in labels)
                and len(labels) == len(set(labels))
                and not labels_seen.intersection(labels),
                "consumption.unique_new_task_method_packages",
            )
            require(
                labels
                == sorted(
                    labels,
                    key=lambda label: (
                        int(label.rsplit("_", 1)[1]),
                        GENERATION_CONDITIONS.index(label.split("_")[0]),
                    ),
                ),
                "consumption.frozen_replicate_order",
            )
            labels_seen.update(labels)
    ready = all(len(eligible[task][method]) >= 4 for task in TASKS for method in METHODS)
    selected = (
        [
            {
                "task_key": task,
                "actual_method": method,
                "label": label,
                "position": index + 1,
                "role": "future_train" if index < 3 else "heldout",
            }
            for task in TASKS
            for method in METHODS
            for index, label in enumerate(eligible[task][method][:4])
        ]
        if ready
        else []
    )
    require(
        selection.get("status")
        == ("RAW_METHOD_SUPPORT_ESTABLISHED" if ready else "INPUT_INADEQUATE")
        and encode(selection.get("selected")) == encode(selected),
        "consumption.frozen_first_four_or_empty",
    )
    require(
        selection.get("training_allowed") is False
        and selection.get("includes_historical_target_packages") is False
        and selection.get("replace_selected_package_after_token_failure") is False
        and selection.get("selected_token_consumability") == "NOT_MEASURED",
        "consumption.support_only_unmeasured_selection",
    )
    return selected


def _package(selected, positives):
    require(
        isinstance(positives, (list, tuple)) and bool(positives), "consumption.positive_package"
    )
    candidates = []
    for pair in positives:
        require(
            isinstance(pair, (list, tuple)) and len(pair) == 2, "consumption.candidate_raw_pair"
        )
        candidate, raw = pair
        tokens._candidate(candidate)
        require(
            isinstance(raw, bytes)
            and candidate["target_response"].encode("utf-8") == raw
            and sha(raw) == candidate["raw_response_sha256"],
            "consumption.original_target_bytes",
        )
        require(
            candidate["session_label"] == selected["label"]
            and candidate["task_key"] == selected["task_key"]
            and candidate["population"] == selected["label"].split("_")[0],
            "consumption.selected_original_session",
        )
        candidates.append(candidate)
    indices = [candidate["response_index"] for candidate in candidates]
    require(
        indices == sorted(set(indices))
        and len({candidate["id"] for candidate in candidates}) == len(candidates)
        and len({candidate["source_closeout_id"] for candidate in candidates}) == 1
        and [candidate["response_kind"] for candidate in candidates].count("Final") == 1
        and candidates[-1]["response_kind"] == "Final",
        "consumption.whole_ordered_positive_package_with_Final",
    )
    # Later actual HTTP histories must contain the exact earlier public targets.
    # This validates consistency, not which unselected failed responses qualify.
    for candidate in candidates:
        messages = candidate["input_messages"]
        require(
            len(messages) == 2 + 2 * candidate["response_index"],
            "consumption.entire_original_request_history",
        )
        for prior in candidates:
            if prior["response_index"] >= candidate["response_index"]:
                break
            history_index = 2 + 2 * prior["response_index"]
            require(
                messages[:history_index] == prior["input_messages"]
                and messages[history_index]
                == {"role": "assistant", "content": prior["target_response"]},
                "consumption.original_cross_response_history",
            )
    return candidates


def _report(
    selection,
    status,
    *,
    checks=(),
    packages=(),
    failures=(),
    binding=None,
    policy=None,
    load_attempts=0,
    tokenizer_loaded=False,
    expected_rows=0,
):
    return record(
        "basis_support_consumption_report",
        status=status,
        source_selection_id=selection["id"],
        source_selection_sha256=sha(encode(selection)),
        selected=selection["selected"],
        selected_original_packages=len(selection["selected"]),
        selected_future_train_packages=sum(
            item["role"] == "future_train" for item in selection["selected"]
        ),
        selected_heldout_packages=sum(item["role"] == "heldout" for item in selection["selected"]),
        package_checks=list(packages),
        token_checks=list(checks),
        failures=list(failures),
        selected_candidate_rows=expected_rows,
        candidate_encoding_attempts=len(checks),
        tokenizer_load_attempts=load_attempts,
        tokenizer_loaded=tokenizer_loaded,
        tokenizer_binding_id=binding["id"] if binding else None,
        representation_policy_id=policy["id"] if policy else None,
        all_selected_packages_checked=len(packages) == 16,
        all_selected_rows_checked=bool(expected_rows) and len(checks) == expected_rows,
        consumability_established=status == "SUPPORT_REPRESENTATION_ESTABLISHED",
        upstream_authority=(
            "caller-sealed financial audit, full mapping, selection and complete source candidates"
        ),
        selection_sealing_verified_by_this_pure_function=False,
        no_replacement_cropping_rewriting_or_prefix_substitution=True,
        requested_g_preserved_separately_from_actual_method=True,
        historical_target_packages_consumed=0,
        historical_token_arrays_read_or_retokenized=0,
        training_population_27_materialized=False,
        training_weights_assigned=False,
        training_allowed=False,
        training_runs=0,
        Student_weight_loads=0,
        Student_forward_calls=0,
        Student_generations=0,
        NLL_calls=0,
        greedy_calls=0,
        heldout_training_NLL_or_greedy_calls=0,
        Provider_calls=0,
        next_step="stop_support_stage_no_automatic_training",
    )


def check_selected(root, selection, candidates, *, loader=load_bound_assets, expected_policy=None):
    """Return one report; load once and encode only the sealed selected original rows.

    ``candidates`` maps labels to source.candidates(session)[0], i.e. ordered
    (new candidate record, original assistant.raw bytes) pairs. Extra pool labels
    are never accessed. Raw insufficiency returns empty checks before touching
    candidates, metadata, or the loader. A source-validation failure also avoids
    tokenizer loading. Once valid inputs are established, every selected positive
    response is attempted once even if another response fails; failure stops the
    support gate without substituting later packages. Caller seals the report.
    """
    selected = _selection(selection)
    if not selected:
        return _report(selection, "INPUT_INADEQUATE")
    require(isinstance(candidates, dict), "consumption.candidate_pool")
    originals, failures = {}, []
    for item in selected:
        label = item["label"]
        try:
            require(label in candidates, "consumption.selected_package_missing")
            originals[label] = _package(item, candidates[label])
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            failures.append(
                {"label": label, "phase": "original_source_validation", "reason": str(error)}
            )
    if failures:
        return _report(selection, "SELECTED_SOURCE_VALIDATION_FAILED", failures=failures)
    expected_rows = sum(len(package) for package in originals.values())
    loaded = False
    try:
        binding, policy, tokenizer = loader(root)
        loaded = True
        require(policy == tokens._policy(binding), "consumption.frozen_loaded_policy")
        require(
            expected_policy is None or policy == expected_policy, "consumption.presealed_policy"
        )
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, ImportError) as error:
        return _report(
            selection,
            "SELECTED_REPRESENTATION_FAILED",
            failures=[{"phase": "tokenizer_loading", "reason": str(error)}],
            load_attempts=1,
            tokenizer_loaded=loaded,
            expected_rows=expected_rows,
        )
    checks, packages = [], []
    for item in selected:
        label = item["label"]
        package_checks = []
        for candidate in originals[label]:
            fields = {
                "candidate_id": candidate["id"],
                "label": label,
                "requested_basis": candidate["population"],
                "actual_method": item["actual_method"],
                "role": item["role"],
                "response_index": candidate["response_index"],
                "raw_response_sha256": candidate["raw_response_sha256"],
            }
            try:
                representation = tokens.encode_candidate(candidate, binding, policy, tokenizer)
                consumable = representation["consumable_token_representation"]
                check = record(
                    "basis_selected_response_check",
                    **fields,
                    status="PASS" if consumable else "FAIL",
                    reason=representation["reason"],
                    representation=representation,
                )
            except (ValueError, TypeError, KeyError, UnicodeError, RuntimeError) as error:
                check = record(
                    "basis_selected_response_check",
                    **fields,
                    status="FAIL",
                    reason=str(error),
                    representation=None,
                )
            checks.append(check)
            package_checks.append(check)
            if check["status"] != "PASS":
                failures.append(
                    {**fields, "phase": "token_representation", "reason": check["reason"]}
                )
        packages.append(
            record(
                "basis_selected_package_check",
                **item,
                source_closeout_id=originals[label][0]["source_closeout_id"],
                requested_basis=originals[label][0]["population"],
                positive_rows=len(package_checks),
                candidate_ids=[check["candidate_id"] for check in package_checks],
                token_check_ids=[check["id"] for check in package_checks],
                status="PASS"
                if all(check["status"] == "PASS" for check in package_checks)
                else "FAIL",
                heldout_representation_only=item["role"] == "heldout",
            )
        )
    return _report(
        selection,
        "SELECTED_REPRESENTATION_FAILED" if failures else "SUPPORT_REPRESENTATION_ESTABLISHED",
        checks=checks,
        packages=packages,
        failures=failures,
        binding=binding,
        policy=policy,
        load_attempts=1,
        tokenizer_loaded=True,
        expected_rows=expected_rows,
    )
