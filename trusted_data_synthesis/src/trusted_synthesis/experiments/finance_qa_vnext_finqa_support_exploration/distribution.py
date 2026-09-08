"""Finite laws for a prospective equal-weight N/D mixture, not equal success strata."""

from collections import Counter
from fractions import Fraction

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require

from .plan import rules
from .projection import compare


def partition(rows, projections, graph_field):
    classes, pairs, unknown = [], [], []
    for row in rows:
        p = projections[row["label"]]
        g = p.get(graph_field)
        if g is None:
            unknown.append(row["label"])
            continue
        found = None
        for group in classes:
            relation = compare(projections[group["representative"]][graph_field], g)
            pair = record(
                "support_graph_comparison",
                graph_kind=graph_field,
                left=group["representative"],
                right=row["label"],
                **relation,
            )
            pairs.append(pair)
            if relation["relation"] == "EQUIVALENT":
                found = group
                group["equivalence_witness_ids"].append(pair["id"])
                break
            require(relation["relation"] == "DIFFERENT", "distribution.same_task_domain")
        if found is None:
            found = {"representative": row["label"], "members": [], "equivalence_witness_ids": []}
            classes.append(found)
        found["members"].append(row["label"])
    states = []
    by_label = {r["label"]: r for r in rows}
    for group in classes:
        origin = Counter(by_label[label]["exploration_stratum"] for label in group["members"])
        states.append(
            record(
                "support_finite_state",
                task_key=rows[0]["task_key"],
                graph_kind=graph_field,
                rule_id=rules()["id"],
                representative_projection_id=projections[group["representative"]]["id"],
                origin_counts=dict(origin),
                origin_given_class={
                    k: str(Fraction(v, len(group["members"]))) for k, v in origin.items()
                },
                **group,
            )
        )
    return states, pairs, unknown


def measure(registrations, audits, projections):
    by_label = {r["label"]: r for r in audits}
    require(len(registrations) == len(by_label) == 12, "distribution.registered_twelve")
    reports, assignments = {}, []

    def unknown_outcome(label):
        row = by_label[label]
        return str(row.get("status", "")).startswith("unknown") or bool(row.get("condition_flags"))

    for task in ("J1", "J2"):
        rows = [r for r in registrations if r["task_key"] == task]
        valid = [r for r in rows if by_label[r["label"]]["complete_valid"]]
        require(len(rows) == 6, "distribution.task_six")
        strata = {}
        unknown_outcomes = [r["label"] for r in rows if unknown_outcome(r["label"])]
        for stratum in ("N", "D"):
            rs = [r for r in rows if r["exploration_stratum"] == stratum]
            require(len(rs) == 3, "distribution.stratum_three")
            m = sum(by_label[r["label"]]["complete_valid"] for r in rs)
            missing = [r["label"] for r in rs if unknown_outcome(r["label"])]
            strata[stratum] = {
                "registered": 3,
                "complete_valid": m,
                "success_fraction": str(Fraction(m, 3)) if not missing else None,
                "unknown_outcomes": missing,
            }
        graph_reports = {}
        for field in ("graph", "support_graph"):
            states, pairs, unknown = partition(valid, projections, field)
            mass = [
                {
                    "state_id": s["id"],
                    "count": len(s["members"]),
                    "mass": str(Fraction(len(s["members"]), len(valid))),
                    "N_count": s["origin_counts"].get("N", 0),
                    "D_count": s["origin_counts"].get("D", 0),
                }
                for s in states
            ]
            component_laws = {}
            for stratum in ("N", "D"):
                m = strata[stratum]["complete_valid"]
                unresolved = [
                    label for label in unknown if by_label[label]["exploration_stratum"] == stratum
                ]
                values = [
                    {"state_id": s["id"], "mass": str(Fraction(s["origin_counts"][stratum], m))}
                    for s in states
                    if s["origin_counts"].get(stratum)
                ]
                component_laws[stratum] = {
                    "valid_denominator": m,
                    "unresolved_labels": unresolved,
                    "pi": values
                    if m and not unresolved and not strata[stratum]["unknown_outcomes"]
                    else None,
                }
            graph_reports[field] = {
                "states": states,
                "pairs": pairs,
                "valid_denominator": len(valid),
                "unknown_labels": unknown,
                "unknown_valid_mass": str(Fraction(len(unknown), len(valid))) if valid else None,
                "known_mass": mass,
                "pi": mass if valid and not unknown and not unknown_outcomes else None,
                "by_stratum": component_laws,
            }
            if field == "graph":
                for row in valid:
                    state = next((s for s in states if row["label"] in s["members"]), None)
                    assignments.append(
                        {
                            "label": row["label"],
                            "task_key": task,
                            "exploration_stratum": row["exploration_stratum"],
                            "status": "MAPPED" if state else "UNDETERMINED",
                            "state_id": state["id"] if state else None,
                        }
                    )
        reports[task] = {
            "registered": 6,
            "complete_valid": len(valid),
            "mixture_success_fraction": str(Fraction(len(valid), 6))
            if not unknown_outcomes
            else None,
            "unknown_outcomes": unknown_outcomes,
            "strata": strata,
            "original_task_weight": "1/2",
            **graph_reports,
        }
    return record(
        "support_exploration_measurement",
        tasks=reports,
        assignments=assignments,
        source_mixture={"N": "1/2", "D": "1/2"},
        successful_strata_not_given_half_weight=True,
        old_V0_V1_samples_used=0,
        task_pooled_class_law=None,
        class_training_weights=None,
        novelty=None,
        contribution=None,
        training_utility=None,
    )
