"""Finite N/E comparisons with full denominators and condition-specific class identities."""

from collections import Counter
from fractions import Fraction
from itertools import combinations

from .plan import ARMS, REPLICATES, TASKS, condition, encode, record, require, sha


def fraction(n, d):
    return str(Fraction(n, d)) if d else None


def measure(rows, projections, chains):
    require(len(rows) == len({r["label"] for r in rows}), "measurement.unique_rows")
    indexed = {p["session_label"]: p for p in projections}
    evidence = {c["label"]: c for c in chains}
    require(set(evidence) == {r["label"] for r in rows}, "measurement.all_registered_chains")
    populations, all_pairs, class_ids = {}, [], {}
    for arm in ARMS:
        tasks = {}
        for task in TASKS:
            subset = [r for r in rows if r["arm"] == arm and r["task_key"] == task]
            require(len(subset) == REPLICATES, "measurement.full_eight_denominator")
            valid = [r for r in subset if r["formula_driven_trace_verified"]]
            groups, unresolved = {}, []
            for row in valid:
                label = row["label"]
                projection = indexed.get(label)
                class_ids[label] = None
                if projection is None or projection["status"] != "MAPPED":
                    unresolved.append(label)
                    continue
                signature = projection["behavior_signature"]
                require(
                    signature["fixed_condition"] == condition(arm)["id"]
                    and projection["population"] == arm
                    and projection["task_key"] == task
                    and projection["source_closeout_id"] == row["id"]
                    and projection["behavior_key"] == sha(encode(signature)),
                    "measurement.full_condition_task_source_identity",
                )
                key = projection["behavior_key"]
                group = groups.setdefault(
                    key,
                    {
                        "signature": signature,
                        "session_labels": [],
                        "behavior_label": evidence[label]["complete_behavior_label"],
                    },
                )
                require(group["signature"] == signature, "measurement.no_hash_only_equivalence")
                group["session_labels"].append(label)
            classes = []
            for _key, group in sorted(groups.items()):
                cid = "NE_complete_behavior_class:" + sha(
                    encode(
                        {
                            "fixed_condition": condition(arm)["id"],
                            "task_key": task,
                            "full_behavior_signature": group["signature"],
                        }
                    )
                )
                for label in group["session_labels"]:
                    class_ids[label] = cid
                classes.append(
                    {
                        **group,
                        "class_id": cid,
                        "count": len(group["session_labels"]),
                        "conditional_mass_over_all_valid": fraction(
                            len(group["session_labels"]), len(valid)
                        ),
                    }
                )
            pair_counts = Counter()
            for left, right in combinations(valid, 2):
                first, second = indexed.get(left["label"]), indexed.get(right["label"])
                status = "UNDETERMINED"
                if all(p is not None and p["status"] == "MAPPED" for p in (first, second)):
                    status = (
                        "EQUIVALENT"
                        if first["behavior_signature"] == second["behavior_signature"]
                        else "DISTINCT"
                    )
                pair_counts[status] += 1
                all_pairs.append(
                    record(
                        "within_condition_valid_pair",
                        arm=arm,
                        task_key=task,
                        labels=[left["label"], right["label"]],
                        status=status,
                        conditions_not_pooled=True,
                        full_signatures_compared=True,
                    )
                )
            layer_rows = [evidence[r["label"]] for r in subset]
            mentions = Counter(c["public_R_mention"]["status"] for c in layer_rows)
            executions = Counter(c["R_execution_status"] for c in layer_rows)
            source = Counter(c["R_source_relation_status"] for c in layer_rows)
            final = Counter(c["R_Final_support_status"] for c in layer_rows)
            behavior = Counter(c["complete_behavior_label"] for c in layer_rows)
            pure_D, pure_R = behavior["PURE_D"], behavior["PURE_R"]
            tasks[task] = {
                "registered": len(subset),
                "valid_count": len(valid),
                "quantity_counts": dict(Counter(r["answer"]["V_quantity"] for r in subset)),
                "format_counts": dict(Counter(r["answer"]["V_format"] for r in subset)),
                "trace_status_counts": dict(Counter(r["trace_status"] for r in subset)),
                "valid_yield": fraction(len(valid), REPLICATES),
                "R_mention_status_counts": dict(mentions),
                "R_execution_status_counts": dict(executions),
                "R_source_relation_status_counts": dict(source),
                "R_Final_support_status_counts": dict(final),
                "confirmed_R_execution_yield": fraction(executions["CONFIRMED"], REPLICATES),
                "valid_pure_R_yield": fraction(pure_R, REPLICATES),
                "complete_behavior_counts": dict(behavior),
                "known_complete_classes": classes,
                "mapping_unresolved_labels": unresolved,
                "mapping_unresolved_mass_over_valid": fraction(len(unresolved), len(valid)),
                "within_condition_valid_pair_status_counts": dict(pair_counts),
                "within_condition_valid_pair_count": len(valid) * (len(valid) - 1) // 2,
                "pure_D_count": pure_D,
                "pure_R_count": pure_R,
                "historical_four_per_class_count_threshold_met": pure_D >= 4 and pure_R >= 4,
                "token_consumability": "NOT_MEASURED",
                "training_input_instantiated": False,
            }
            require(
                sum(c["count"] for c in classes) + len(unresolved) == len(valid),
                "measurement.valid_mass_not_renormalized_over_mapped_subset",
            )
        populations[arm] = {
            "condition_id": condition(arm)["id"],
            "tasks": tasks,
            "registered": sum(t["registered"] for t in tasks.values()),
            "valid_count": sum(t["valid_count"] for t in tasks.values()),
            "is_original_unmodified_T_natural_distribution": False,
        }
    contrasts = {}
    for task in TASKS:
        N, E = populations["N"]["tasks"][task], populations["E"]["tasks"][task]
        contrasts[task] = {
            "E_minus_N_confirmed_R_execution_yield": str(
                Fraction(E["confirmed_R_execution_yield"])
                - Fraction(N["confirmed_R_execution_yield"])
            ),
            "E_minus_N_valid_pure_R_yield": str(
                Fraction(E["valid_pure_R_yield"]) - Fraction(N["valid_pure_R_yield"])
            ),
            "descriptive_fixed_batch_difference_not_paired_provider_randomness": True,
            "does_not_estimate_Student_utility_or_Contribution": True,
        }
    return record(
        "NE_finite_measurement",
        populations=populations,
        contrasts=contrasts,
        session_class_ids=class_ids,
        within_condition_valid_pairs=all_pairs,
        all_failed_unknown_unfinished_registrations_retained=True,
        no_cross_condition_class_pooling_or_training_selection=True,
        finite_sample_support_not_exhaustive_natural_support=True,
    )
