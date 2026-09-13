"""Fixed-denominator descriptive coverage; never weights or training selection."""

from collections import Counter, defaultdict

from ..finance_qa_vnext_catalog_bridge.worker import record as old_record
from . import protocol as p


def _hist(values):
    return dict(sorted(Counter(values).items()))


def _summary(rows):
    flags = (
        "attempted",
        "first_Final",
        "quantity_PASS",
        "financial_valid",
        "actual_movement",
        "financial_movement",
        "complete_mapped_movement",
        "token_consumable_movement",
        "complete_mapped_endpoint",
        "token_consumable_endpoint",
        "unique_component_any_read",
        "unique_component_in_Final",
        "source_unbound_in_Final",
        "token_diagnostic_attempted",
    )
    counts = {key: sum(row[key] for row in rows) for key in flags}
    return {
        "registered_denominator": len(rows),
        **counts,
        "actual_method_counts": _hist(row["actual_method"] for row in rows),
        "reason_counts": _hist(row["reason"] or "<none>" for row in rows),
        "diagnosis_counts": _hist(row["diagnosis"] for row in rows),
        "terminal_counts": _hist(row["terminal"] for row in rows),
        "observed_financial_movement_fraction_registered": counts["financial_movement"] / len(rows),
        "observed_consumable_movement_fraction_registered": counts["token_consumable_movement"]
        / len(rows),
        "rates_are_registered_sample_fractions_not_population_probabilities": True,
    }


def _groups(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return [
        {**dict(zip(keys, key, strict=True)), **_summary(values)}
        for key, values in sorted(groups.items())
    ]


def summarize(registry, results, token_diagnostics):
    p.require(
        len(registry) == len(results) == p.SESSION_CAP
        and len({x["session_id"] for x in registry}) == p.SESSION_CAP,
        "full_144_denominator",
    )
    p.checked(token_diagnostics, "probe_token_diagnostics")
    token_rows = token_diagnostics["packages"]
    tokens = {}
    for row in token_rows:
        p.checked(row, "probe_token_package_diagnostic")
        p.require(
            row["registered_session_id"] not in tokens and row["training_eligible"] is False,
            "unique_probe_only_token_diagnostics",
        )
        tokens[row["registered_session_id"]] = row
    rows = []
    for index, (reg, result) in enumerate(zip(registry, results, strict=True)):
        p.require(
            reg["ordinal"] == index and result["registered_session_id"] == reg["session_id"],
            "unchanged_registered_result_order",
        )
        observed = result.get("session")
        q = result.get("qualification")
        row = {
            key: reg[key]
            for key in ("task_id", "family", "quantity", "profile", "basis", "replicate")
        }
        row.update(
            ordinal=index,
            registered_session_id=reg["session_id"],
            attempted=observed is not None,
            first_Final=False,
            quantity_PASS=False,
            financial_valid=False,
            actual_method="NOT_REQUESTED",
            reason="not_requested",
            terminal="not_requested_after_global_stop",
            actual_movement=False,
            financial_movement=False,
            complete_mapped_movement=False,
            token_consumable_movement=False,
            complete_mapped_endpoint=False,
            token_consumable_endpoint=False,
            unique_component_any_read=False,
            unique_component_in_Final=False,
            source_unbound_in_Final=False,
            token_diagnostic_attempted=False,
            token_status="NOT_MEASURED",
            full_class_key=None,
            session_id=None,
            qualification_id=None,
            diagnosis="NOT_REQUESTED",
        )
        if observed is not None:
            p.checked(observed, "probe_session")
            p.checked(q, "probe_qualification")
            old = q["original_semantic_assessment"]
            p.require(
                old
                == old_record(
                    "assessment",
                    **{k: v for k, v in old.items() if k not in {"id", "schema_version"}},
                ),
                "original_semantic_record_identity",
            )
            p.require(
                observed["registered_session"] == reg
                and q["session_id"] == observed["id"]
                and q["task_id"] == reg["task_id"]
                and q["requested_basis"] == reg["basis"]
                and q["profile"] == reg["profile"]
                and q["training_eligible"] is False
                and all(
                    q[key] == old[key]
                    for key in (
                        "actual_method",
                        "financial_valid",
                        "quantity_status",
                        "support_status",
                        "full_mapping_status",
                        "full_class",
                        "reason",
                    )
                ),
                "exact_original_qualification_and_registered_Probe",
            )
            signal = q["structural_signals"]
            component_reads = [
                d["result_id"]
                for d in signal["all_public_tool_diagnostics"]
                if d.get("source", {}).get("status") == "UNIQUE_SOURCE_LOCATOR"
                and d["source"]["roles"].get("movement_exclusive_input")
            ]
            closure = set(signal["first_final_closure_result_ids"])
            financial = q["financial_valid"] is True
            mapped = q["token_diagnostic_eligible"] is True
            movement = q["actual_method"] == "movement"
            token = tokens.get(reg["session_id"])
            if token:
                p.require(
                    token["session_id"] == observed["id"]
                    and token["qualification_id"] == q["id"]
                    and mapped,
                    "token_diagnostic_qualification_join",
                )
            row.update(
                session_id=observed["id"],
                qualification_id=q["id"],
                first_Final=observed["first_final_index"] is not None,
                quantity_PASS=q["quantity_status"] == "PASS",
                financial_valid=financial,
                actual_method=q["actual_method"],
                reason=q["reason"],
                terminal=observed["terminal"],
                actual_movement=movement,
                financial_movement=movement and financial,
                complete_mapped_movement=movement and mapped,
                token_consumable_movement=bool(movement and token and token["consumable"]),
                complete_mapped_endpoint=q["actual_method"] == "endpoint" and mapped,
                token_consumable_endpoint=bool(
                    q["actual_method"] == "endpoint" and token and token["consumable"]
                ),
                unique_component_any_read=bool(component_reads),
                unique_component_in_Final=bool(set(component_reads) & closure),
                source_unbound_in_Final=bool(
                    signal["closure_source_status_counts"].get("UNBOUND_SOURCE", 0)
                ),
                token_diagnostic_attempted=token is not None,
                token_status="PASS"
                if token and token["consumable"]
                else "NOT_CONSUMABLE"
                if token
                else "NOT_MEASURED",
                full_class_key=p.sha(p.encode(q["full_class"])) if mapped else None,
            )
            if row["token_consumable_movement"]:
                diagnosis = "AUTHENTIC_MAPPED_CONSUMABLE_MOVEMENT_PROBE_ONLY"
            elif row["complete_mapped_movement"]:
                diagnosis = "MAPPED_MOVEMENT_TOKEN_NOT_ESTABLISHED"
            elif row["financial_movement"]:
                diagnosis = "FINANCIAL_MOVEMENT_COMPLETE_MAPPING_OR_ORIGIN_NOT_ESTABLISHED"
            elif row["unique_component_in_Final"]:
                diagnosis = "COMPONENT_REFERENCED_FINANCIAL_MOVEMENT_NOT_ESTABLISHED"
            elif row["unique_component_any_read"]:
                diagnosis = "COMPONENT_SIDE_READ_NOT_FINAL_SUPPORT"
            elif row["source_unbound_in_Final"]:
                diagnosis = "UNBOUND_SOURCE_INTENT_NOT_RESOLVED"
            elif not row["first_Final"]:
                diagnosis = "NO_FIRST_FINAL"
            else:
                diagnosis = "NO_UNIQUE_COMPONENT_SUPPORT_OBSERVED"
            row["diagnosis"] = diagnosis
        else:
            p.require(
                q is None and reg["session_id"] not in tokens, "unrequested_not_scored_or_encoded"
            )
        rows.append(row)
    p.require(set(tokens) <= {x["registered_session_id"] for x in rows}, "no_extra_token_packages")
    coverage = []
    for profile in p.PROFILES:
        for task in sorted({r["task_id"] for r in registry}):
            subset = [r for r in rows if r["task_id"] == task and r["profile"] == profile]
            p.require(
                len(subset) == len(p.BASES) * p.REPLICATES, "task_profile_fixed_four_rollouts"
            )
            methods = {r["actual_method"] for r in subset if r["full_class_key"] is not None}
            consumable = {r["actual_method"] for r in subset if r["token_status"] == "PASS"}
            coverage.append(
                {
                    "profile": profile,
                    "task_id": task,
                    "registered_rollouts": len(subset),
                    "complete_mapped_methods": sorted(methods),
                    "consumable_methods": sorted(consumable),
                    "two_method_mapped_support": set(p.BASES) <= methods,
                    "two_method_consumable_support": set(p.BASES) <= consumable,
                    "unique_old_fine_classes": len(
                        {r["full_class_key"] for r in subset if r["full_class_key"]}
                    ),
                }
            )
    return p.record(
        "coverage_metrics",
        registered_rollouts=p.SESSION_CAP,
        totals=_summary(rows),
        by_profile=_groups(rows, ("profile",)),
        by_profile_guidance=_groups(rows, ("profile", "basis")),
        by_family_quantity_profile_guidance=_groups(
            rows, ("family", "quantity", "profile", "basis")
        ),
        task_profile_coverage=coverage,
        all_registered_results=rows,
        tokenizer_diagnostics_id=token_diagnostics["id"],
        training_admitted=False,
        actual_method_is_not_guidance=True,
        financial_validity_is_not_structural_signal=True,
        mapper_is_old_finite_mapper_not_anchored_state_catalog=True,
        two_replicates_per_task_profile_guidance_do_not_establish_population_probability=True,
        hypothesis_tests_or_best_profile_selection_performed=False,
        coverage_discovery_does_not_replace_original_common_AB_or_8_plus_2_gates=True,
    )
