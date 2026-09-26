"""Issuer-cluster paired statistics for the separately registered CN/HK calibration.

Reuse only the frozen exact-arithmetic bootstrap kernel. Validate genuine opaque
issuer identities rather than map securities to invented CIKs. No original
module globals are mutated. All four comparisons share exactly the same draws;
these are legal-issuer clusters, not a claim of economic independence.
"""

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from types import FunctionType

import fixed_kernel_direction_calibration_statistics_20260926 as core

GROUPS, SEEDS, ARMS = core.GROUPS, core.SEEDS, core.ARMS
DECODING_REPEATS, COMPARISONS = core.DECODING_REPEATS, core.COMPARISONS


def require(condition, reason):
    if not condition:
        raise ValueError("cross_market_statistics." + reason)


def canonical_cluster(value):
    require(
        isinstance(value, str) and re.fullmatch(r"issuer:[0-9a-f]{64}", value),
        "evidenced_opaque_issuer_id_required",
    )
    return value


def admission_mapping(admission):
    require(isinstance(admission, Mapping), "issuer_admission_required")
    body = {k: v for k, v in admission.items() if k != "id"}
    encoded = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    require(
        body.get("schema_version") == "cross_market_calibration.v1.cross_market_issuer_admission"
        and admission.get("id")
        == "cross_market_issuer_admission:" + hashlib.sha256(encoded).hexdigest(),
        "issuer_admission_identity",
    )
    rows = admission.get("rows", [])
    mapping = {}
    for row in rows:
        security = row["security_id"]
        require(security not in mapping, "duplicate_security_in_issuer_admission")
        mapping[security] = row
        if row["admitted"]:
            canonical_cluster(row["issuer_cluster_id"])
            require(
                bool(row["legal_name"]) and bool(row["document_bindings"]),
                "issuer_admission_missing_legal_evidence",
            )
            documents = [r["raw_object_id"] for r in row["document_bindings"]]
            require(len(set(documents)) == len(documents), "duplicate_identity_document")
    return mapping


def validate(tasks, outcomes, expected_group_sizes, mapping):
    registry, scores = {}, {}
    for row in tasks:
        require(isinstance(row, Mapping), "task_must_be_mapping")
        require(
            {"task_id", "group", "security_id", "issuer_cluster_id", "raw_object_ids"}
            <= row.keys(),
            "missing_task_field",
        )
        require(not {"cik", "CIK"} & row.keys(), "no_fabricated_CIK_fields")
        task, group = row["task_id"], row["group"]
        require(isinstance(task, str) and bool(task), "invalid_task_id")
        require(task not in registry, "duplicate_task")
        require(isinstance(group, str) and group in GROUPS, "unknown_group")
        cluster = canonical_cluster(row["issuer_cluster_id"])
        security = row["security_id"]
        require(
            security in mapping and mapping[security]["admitted"] is True,
            "task_issuer_not_admitted",
        )
        issuer = mapping[security]
        require(
            issuer.get("exposure", {}).get("project_source_identity_screen_passed") is True,
            "task_project_history_screen_not_admitted",
        )
        require(issuer["issuer_cluster_id"] == cluster, "changed_task_issuer_cluster")
        bound = {d["raw_object_id"] for d in issuer["document_bindings"] if d["admitted"] is True}
        require(
            isinstance(row["raw_object_ids"], list)
            and bool(row["raw_object_ids"])
            and set(row["raw_object_ids"]) <= bound,
            "task_document_identity_not_admitted",
        )
        if "source_cluster" in row:
            require(row["source_cluster"] == cluster, "changed_task_source_cluster")
        registry[task] = group, cluster
    require(
        Counter(group for group, _ in registry.values()) == Counter(expected_group_sizes),
        "fixed_group_task_counts",
    )
    for row in outcomes:
        require(isinstance(row, Mapping), "outcome_must_be_mapping")
        require(
            {"task_id", "seed", "arm", "decoding", "repeat", "Q"} <= row.keys(),
            "missing_outcome_field",
        )
        require(not {"cik", "CIK"} & row.keys(), "no_fabricated_CIK_fields")
        task, seed, arm = row["task_id"], row["seed"], row["arm"]
        mode, repeat, value = row["decoding"], row["repeat"], row["Q"]
        require(isinstance(task, str) and task in registry, "unknown_task")
        require(type(seed) is int and seed in SEEDS, "unknown_seed")
        require(isinstance(arm, str) and arm in ARMS, "unknown_arm")
        require(isinstance(mode, str) and mode in DECODING_REPEATS, "unknown_decoding")
        require(type(repeat) is int and repeat in DECODING_REPEATS[mode], "invalid_repeat")
        require(type(value) in (bool, int) and value in (0, 1), "nonbinary_Q")
        group, cluster = registry[task]
        for field, expected in (
            ("group", group),
            ("issuer_cluster_id", cluster),
            ("source_cluster", cluster),
        ):
            if field in row:
                require(row[field] == expected, "changed_outcome_" + field)
        if "stochastic" in row:
            require(
                type(row["stochastic"]) is bool and row["stochastic"] == (mode == "stochastic"),
                "changed_decoding_flag",
            )
        key = task, seed, arm, mode, repeat
        require(key not in scores, "duplicate_outcome")
        scores[key] = int(value)
    require(len(scores) == len(registry) * 27, "missing_outcomes")
    return registry, scores


def _analyze(tasks, outcomes, admission, *, sizes, replicates, max_draws, production):
    mapping = admission_mapping(admission)

    def bound_validate(tasks, outcomes, expected_group_sizes):
        return validate(tasks, outcomes, expected_group_sizes, mapping)

    # The unchanged numeric kernel works on opaque cluster strings; no securities
    # are translated to CIKs. Its legacy labels are converted only at the boundary.
    namespace = {**vars(core), "_validate": bound_validate}
    kernel = FunctionType(core._analyze.__code__, namespace, "issuer_cluster_kernel")
    value = kernel(
        tasks,
        outcomes,
        expected_group_sizes=sizes,
        replicates=replicates,
        max_draws=max_draws,
        production=production,
    )
    value["schema_version"] = "cross_market_calibration_statistics.20260926.v1"
    value["analysis_scope"] = (
        "cross_market_short_run_transfer_calibration" if production else "synthetic_test_only"
    )
    value["issuer_admission_id"] = admission["id"]
    value["cross_market_stochastic_support"] = value.pop("mechanism_support")
    value["cross_market_greedy_support"] = value.pop("short_run_greedy_support")
    bootstrap = value["bootstrap"]
    bootstrap["unit"] = "evidenced_legal_issuer_cluster"
    bootstrap["issuer_cluster_ids"] = bootstrap.pop("ciks")
    bootstrap["cluster_order"] = "lexicographic_ascending_opaque_issuer_cluster_id"
    for comparison in value["comparisons"].values():
        for group in comparison["group_estimates"]:
            group["issuer_cluster_count"] = group.pop("cik_count")
    value["interpretation"].update(
        source_market="fixed_CNInfo_HKEX_roster_not_original_US_confirmation",
        legal_issuer_clusters_are_not_economically_independent=True,
        related_parent_subsidiary_issuers_may_remain_correlated=True,
        base_model_pretraining_exposure_known=False,
        source_novelty_scope="admitted_frozen_project_source_registry_only",
        original_feedback_distribution_training_value_confirmed=False,
    )
    return value


def analyze(tasks, outcomes, issuer_admission):
    """Strict 180 tasks/4860 binary outcomes; no production tuning parameters."""
    return _analyze(
        tasks,
        outcomes,
        issuer_admission,
        sizes=dict.fromkeys(GROUPS, 60),
        replicates=20000,
        max_draws=200000,
        production=True,
    )


def analyze_synthetic_for_test(tasks, outcomes, issuer_admission, *, sizes, replicates, max_draws):
    return _analyze(
        tasks,
        outcomes,
        issuer_admission,
        sizes=sizes,
        replicates=replicates,
        max_draws=max_draws,
        production=False,
    )
