"""Read-only V24 public-population audit; never reads references or dev scores.

Freezes grouping rules before extraction. Standard-library only: no model,
tokenizer, network, API, private-reference loader, or experiment runtime import.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STUDY = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928"
V18 = STUDY / "finqa_v6_01/v18_researcher_continuation_01"
DEFAULT_OUTPUT = V18 / "v24_data_distribution_audit_01"
LINEAGE_WHITELIST = (
    "dataset",
    "original_id",
    "original_split",
    "company",
    "year",
    "report",
    "source_group",
)
INTENT_PATTERNS = {
    "percent_change": (
        r"\b(?:(?:percent(?:age)?|rate)\s+(?:of\s+)?"
        r"(?:change|increase|decrease|growth|decline|reduction)|"
        r"(?:change|increase|decrease|growth|decline|reduction)\s+(?:in\s+)?"
        r"percent(?:age)?|growth\s+rate|rate\s+of\s+growth)\b"
    ),
    "difference_change": (
        r"\b(?:difference|change|changed|increase|increased|decrease|decreased|"
        r"growth|decline|declined|reduction|reduced|more|less|higher|lower)\b"
    ),
    "ratio_percentage": (
        r"\b(?:ratio|percent|percentage|proportion|fraction|share|portion|rate)\b|%"
    ),
    "sum_total": r"\b(?:sum|total|combined|aggregate)\b",
    "average": r"\b(?:average|mean)\b",
    "minmax": r"\b(?:minimum|maximum|min|max|highest|lowest|largest|smallest|greatest|least)\b",
    "count": r"\b(?:how many|number of|count)\b",
}
INPUT_BINS = [(2000, "<=2000"), (5000, "2001-5000"), (10000, "5001-10000"), (None, ">10000")]
QUESTION_BINS = [(79, "<=79"), (119, "80-119"), (199, "120-199"), (None, ">=200")]
GROUP_FIELDS = (
    "company",
    "report_group",
    "year",
    "intent_proxy",
    "input_size_bin",
    "question_size_bin",
)
EXPECTED_COUNTS = {
    "original_train6251": 6251,
    "sft1000": 1000,
    "native820": 820,
    "train744": 744,
    "excluded256": 256,
    "native_excluded76": 76,
    "native_absent180": 180,
    "feedback350": 350,
    "calibration120": 120,
    "dev883": 883,
    "test1147": 1147,
    "train_multi229": 229,
    "train_chiflex87": 87,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    path = Path(path)
    require("private.references" not in str(path), "private reference reads forbidden")
    require("v23_confirmation" not in str(path), "V23 artifacts out of scope")
    return json.loads(path.read_text())


def source_binding(path):
    path = Path(path)
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_once(path, value):
    """Never replace a prior audit artifact, including a frozen grouping rule."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(read_json(path) == value, f"existing immutable artifact differs: {path}")
        return
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")


def rule_body():
    return {
        "schema": "v24_public_grouping_rules.v1",
        "intent": {
            "patterns": INTENT_PATTERNS,
            "priority": list(INTENT_PATTERNS),
            "fallback": "other",
            "flags": "re.IGNORECASE; all matches separately retained",
            "meaning": "public-question lexical intent proxy; not gold operation or difficulty",
        },
        "input_chars": (
            "len(question) + sum(len(json.dumps(source.content, ensure_ascii=False, "
            "separators=(',', ':'))) for source in public.sources); Unicode codepoints, "
            "no tokenizer; includes quoted text serialization"
        ),
        "input_bins": INPUT_BINS,
        "question_chars": "len(public.question), Unicode codepoints",
        "question_bins": QUESTION_BINS,
        "tables": (
            "public.sources where kind == table; content must be list of lists; "
            "table_rows=sum row counts including headers, table_columns=max row length; "
            "invalid table omitted and count reported"
        ),
        "source_taxonomy": {
            "company": (
                "original lineage.company exact, verified against original_id first path segment"
            ),
            "report_group": "original lineage.source_group exact = finqa:report:<company>/<year>",
            "report": "original lineage.report = <company>/<year>",
            "year": (
                "original lineage.year exact string, "
                "verified against original_id second path segment"
            ),
        },
        "lineage_whitelist": LINEAGE_WHITELIST,
        "task_key": "dataset + '/' + task_id (original canonical slash format)",
        "group_fields": GROUP_FIELDS,
        "weights": (
            "one equal weight per task; native820/training subsets defined only by "
            "preexisting sealed eligibility/support"
        ),
        "concentration": (
            "HHI=sum task share squared; inverse HHI is equivalent source diversity, "
            "NOT statistical effective sample size; top1/top5/top10 mass and "
            "linear-interpolated group-size quantiles"
        ),
        "distribution_distance": (
            "TV=0.5*sum(abs(p-q)); JS=0.5*KL2(p||m)+0.5*KL2(q||m), m=(p+q)/2; "
            "0*log(0)=0, absent categories probability0; range[0,1]"
        ),
        "common_support_effect_contract": {
            "fields": ["intent_proxy", "input_size_bin"],
            "separate_marginal_groups_not_joint_cells": True,
            "target": ["sft1000", "train744", "train_multi229", "train_chiflex87"],
            "minimum_dev_group_tasks": 20,
            "common_support": (
                "only categories with target mass>0 AND dev task count>=20; "
                "report retained target mass and raw dev task mass; "
                "renormalize target mass within retained support"
            ),
            "formula": (
                "sum_g target_mass(g)/target_common_mass * mean_dev_g(Full-Static); "
                "descriptive covariate-standardized contrast, "
                "not population generalization or causal transport"
            ),
        },
        "dev_effect_suppression": {
            "minimum_group_tasks": 20,
            "smaller_groups": "counts only, no selected efficacy claim",
            "top_sources": "highest dev task counts, tie lexicographic; never highest gains",
            "negative_controls": ["Manual+ - Manual-", "Full - C-only"],
        },
        "scope": {
            "private_reference_reads": False,
            "lineage_strata_access": False,
            "dev_score_reads_by_this_script": False,
            "test_correctness_reads": False,
            "test_public_features_only": True,
            "api_calls": 0,
            "gpu_calls": 0,
            "v23_mutations": False,
            "original_experiment_mutations": False,
            "historical_dev_results_already_known_to_project": True,
            "new_rules_frozen_before_new_group_correctness_join": True,
        },
    }


def freeze(output):
    path = Path(output) / "grouping_protocol.json"
    body = json.loads(json.dumps(rule_body()))
    rules_id = digest(body)
    if path.exists():
        value = read_json(path)
        require(
            value["rules"] == body and value["rules_id"] == rules_id,
            "frozen grouping rules cannot change",
        )
        require(
            value["id"] == digest({k: v for k, v in value.items() if k != "id"}),
            "grouping protocol digest mismatch",
        )
        return value
    value = {
        "schema": "v24_frozen_grouping_protocol.v1",
        "frozen_at": now(),
        "rules_id": rules_id,
        "rules": body,
    }
    value["id"] = digest(value)
    write_once(path, value)
    return value


def size_bin(size, bins):
    return next(label for upper, label in bins if upper is None or size <= upper)


def public_lineage_metadata(raw_lineage):
    """Project only approved provenance keys, never iterate/read gold strata."""
    return {key: raw_lineage[key] for key in LINEAGE_WHITELIST}


def task_features(task, lineage, role):
    require(task["dataset"] == lineage["dataset"] == "finqa", "only fixed FinQA public snapshot")
    task_id = task["task_id"]
    require(task_id == lineage["original_id"], "public and lineage row identities differ")
    pieces = task_id.split("/")
    company, year = lineage["company"], str(lineage["year"])
    report = company + "/" + year
    require(
        pieces[:2] == [company, year]
        and lineage["report"] == report
        and lineage["source_group"] == "finqa:report:" + report,
        "source taxonomy differs from original_id",
    )
    question = task["question"]
    flags = [
        name
        for name, pattern in INTENT_PATTERNS.items()
        if re.search(pattern, question, re.IGNORECASE)
    ]
    chars = len(question) + sum(
        len(json.dumps(s["content"], ensure_ascii=False, separators=(",", ":")))
        for s in task["sources"]
    )
    tables = [s["content"] for s in task["sources"] if s["kind"] == "table"]
    valid = [t for t in tables if isinstance(t, list) and all(isinstance(row, list) for row in t)]
    return {
        "task_id": task_id,
        "role": role,
        "dataset": "finqa",
        "original_split": lineage["original_split"],
        "company": company,
        "report_group": lineage["source_group"],
        "report": report,
        "year": year,
        "intent_proxy": flags[0] if flags else "other",
        "intent_flags": flags,
        "input_chars": chars,
        "input_size_bin": size_bin(chars, INPUT_BINS),
        "question_chars": len(question),
        "question_size_bin": size_bin(len(question), QUESTION_BINS),
        "table_count": len(valid),
        "invalid_table_count": len(tables) - len(valid),
        "table_rows": sum(len(t) for t in valid),
        "table_columns": max((len(row) for t in valid for row in t), default=0),
    }


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * q
    low = int(position)
    return values[low] + (position - low) * (values[min(low + 1, len(values) - 1)] - values[low])


def concentration(counts):
    total = sum(counts.values())
    if not total:
        return {"tasks": 0, "sources": 0, "hhi": None, "equivalent_source_diversity": None}
    sizes = sorted(counts.values(), reverse=True)
    hhi = sum((value / total) ** 2 for value in sizes)
    return {
        "tasks": total,
        "sources": len(counts),
        "hhi": hhi,
        "equivalent_source_diversity": 1 / hhi,
        "not_statistical_ESS": True,
        "top1_mass": sum(sizes[:1]) / total,
        "top5_mass": sum(sizes[:5]) / total,
        "top10_mass": sum(sizes[:10]) / total,
        "group_size_quantiles": {
            str(q): quantile(sizes, q) for q in (0, 0.25, 0.5, 0.75, 0.9, 0.95, 1)
        },
        "max_group_size": sizes[0],
        "top_sources": [
            {"source": k, "tasks": v, "mass": v / total}
            for k, v in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
    }


def distribution(keys, features, field):
    return dict(sorted(Counter(features[key][field] for key in keys).items()))


def distance(left, right):
    a, b = sum(left.values()), sum(right.values())
    if not a or not b:
        return {"tv": None, "js_base2": None}
    tv = js = 0.0
    for key in sorted(set(left) | set(right)):
        p, q = left.get(key, 0) / a, right.get(key, 0) / b
        m = (p + q) / 2
        tv += abs(p - q) / 2
        if p:
            js += 0.5 * p * math.log2(p / m)
        if q:
            js += 0.5 * q * math.log2(q / m)
    return {"tv": tv, "js_base2": js}


def overlap(left, right, features, field):
    a, b = distribution(left, features, field), distribution(right, features, field)
    shared = set(a) & set(b)
    return {
        "shared_sources": len(shared),
        "left_sources": len(a),
        "right_sources": len(b),
        "left_task_mass_in_shared_sources": sum(a[k] for k in shared) / len(left),
        "right_task_mass_in_shared_sources": sum(b[k] for k in shared) / len(right),
        "task_id_intersection": len(set(left) & set(right)),
    }


def summarize(features, populations):
    summaries = {}
    for name, keys in populations.items():
        groups = {field: distribution(keys, features, field) for field in GROUP_FIELDS}
        summaries[name] = {
            "tasks": len(keys),
            "unique_task_keys": len(set(keys)),
            "distributions": groups,
            "source_concentration": {
                field: concentration(groups[field]) for field in ("company", "report_group")
            },
            "numeric_feature_quantiles": {
                field: {
                    str(q): quantile([features[k][field] for k in keys], q)
                    for q in (0, 0.25, 0.5, 0.75, 0.9, 0.95, 1)
                }
                for field in ("input_chars", "question_chars", "table_rows", "table_columns")
            },
            "intent_multilabel_counts": dict(
                sorted(
                    Counter(flag for key in keys for flag in features[key]["intent_flags"]).items()
                )
            ),
        }
    pairs = [
        (a, b)
        for a in ("sft1000", "train744", "feedback350", "calibration120")
        for b in ("dev883", "test1147")
    ] + list(itertools.combinations(("sft1000", "feedback350", "calibration120"), 2))
    overlaps = {
        a + "__" + b: {
            field: overlap(populations[a], populations[b], features, field)
            for field in ("company", "report_group")
        }
        for a, b in pairs
    }
    distances = {
        a + "__" + b: {
            field: distance(
                summaries[a]["distributions"][field], summaries[b]["distributions"][field]
            )
            for field in GROUP_FIELDS
        }
        for a, b in itertools.combinations(populations, 2)
    }
    retention = {}
    for source, target in (
        ("original_train6251", "sft1000"),
        ("sft1000", "native820"),
        ("native820", "train744"),
        ("sft1000", "train744"),
        ("train744", "train_multi229"),
        ("train744", "train_chiflex87"),
    ):
        require(
            set(populations[target]) <= set(populations[source]), "retention populations not nested"
        )
        retention[source + "__" + target] = {
            "source_tasks": len(populations[source]),
            "retained_tasks": len(populations[target]),
            "retention_rate": len(populations[target]) / len(populations[source]),
            "groups": {
                field: {
                    group: {
                        "source_tasks": count,
                        "retained_tasks": summaries[target]["distributions"][field].get(group, 0),
                        "retention_rate": summaries[target]["distributions"][field].get(group, 0)
                        / count,
                    }
                    for group, count in summaries[source]["distributions"][field].items()
                }
                for field in GROUP_FIELDS
            },
        }
    return {
        "populations": summaries,
        "role_source_overlap": overlaps,
        "distribution_distances": distances,
        "retention": retention,
    }


def run(output=DEFAULT_OUTPUT):
    output = Path(output)
    protocol = freeze(output)
    public_path = STUDY / "snapshots/finqa/public.jsonl"
    lineage_path = STUDY / "snapshots/finqa/lineage.jsonl"
    original_path = STUDY / "finqa_v6_01/experiment0_01/protocol.json"
    generation_path = STUDY / "finqa_v6_01/v10_new8000_01/registration/protocol.json"
    native_path = STUDY / "finqa_v6_01/v10_new8000_01/native_support/record.json"
    support_path = V18 / "material/support/record.json"
    original, generation, native, support = [
        read_json(p) for p in (original_path, generation_path, native_path, support_path)
    ]
    assignments = original["role_plan"]["assignments"]
    require(
        generation["snapshot"] == original["snapshot"] == str(public_path.parent),
        "original snapshot identity differs",
    )
    require(set(generation["task_ids"]) == set(original["task_ids"]), "original SFT roster changed")
    require(native["protocol_id"] == generation["id"], "native roster protocol mismatch")
    bindings = {
        name: source_binding(path)
        for name, path in {
            "public": public_path,
            "lineage": lineage_path,
            "original_role_protocol": original_path,
            "new_generation_protocol": generation_path,
            "native_eligibility": native_path,
            "v18_training_support": support_path,
        }.items()
    }
    manifest_path = public_path.parent / "manifest.json"
    manifest = read_json(manifest_path)
    bindings["snapshot_manifest"] = source_binding(manifest_path)
    require(
        manifest["id"] == original["snapshot_id"] == generation["snapshot_id"],
        "fixed snapshot manifest identity differs",
    )
    require(
        manifest["files"]["public.jsonl"]["sha256"] == bindings["public"]["sha256"]
        and manifest["files"]["lineage.jsonl"]["sha256"] == bindings["lineage"]["sha256"],
        "public/lineage bytes changed from fixed snapshot",
    )
    features = {}
    public_access_at = now()
    with public_path.open() as tasks, lineage_path.open() as lineages:
        for task_line, lineage_line in zip(tasks, lineages, strict=True):
            task = json.loads(task_line)
            # Only whitelisted metadata survives parsing; never inspect strata.
            raw_lineage = json.loads(lineage_line)
            lineage = public_lineage_metadata(raw_lineage)
            del raw_lineage
            key = task["dataset"] + "/" + task["task_id"]
            require(key not in features, "duplicate task key must not be silently collapsed")
            features[key] = task_features(task, lineage, assignments[key])
    require(
        len(features) == 8281 and set(features) == set(assignments),
        "complete original public roster required",
    )

    def canonical(ids):
        return sorted("finqa/" + task_id for task_id in ids)

    def selected(field, value):
        return sorted(k for k, f in features.items() if f[field] == value)

    populations = {
        "original_train6251": selected("original_split", "train"),
        "sft1000": selected("role", "sft"),
        "native820": canonical(native["native_supported_tasks"]),
        "train744": canonical(support["training_task_ids"]),
        "feedback350": selected("role", "feedback"),
        "calibration120": selected("role", "calibration"),
        "dev883": selected("role", "development"),
        "test1147": selected("role", "test"),
        "train_multi229": canonical(
            k for k, s in support["task_support"].items() if len(s["states"]) > 1
        ),
        "train_chiflex87": canonical(
            k for k, s in support["task_support"].items() if set(s["chi"].values()) == {0, 1}
        ),
    }
    populations["excluded256"] = sorted(set(populations["sft1000"]) - set(populations["train744"]))
    populations["native_excluded76"] = sorted(
        set(populations["native820"]) - set(populations["train744"])
    )
    populations["native_absent180"] = sorted(
        set(populations["sft1000"]) - set(populations["native820"])
    )
    require(
        populations["sft1000"] == canonical(original["task_ids"]),
        "SFT role and original fixed task roster differ",
    )
    require(
        {name: len(keys) for name, keys in populations.items()} == EXPECTED_COUNTS,
        "fixed population counts differ",
    )
    require(
        set(support["task_support"]) == set(support["training_task_ids"]),
        "V18 support task roster mismatch",
    )
    require(
        all(
            len(keys) == len(set(keys)) and set(keys) <= set(features)
            for keys in populations.values()
        ),
        "invalid task roster",
    )
    feature_value = {
        "schema": "v24_public_features.v1",
        "protocol_id": protocol["id"],
        "rules_id": protocol["rules_id"],
        "source_bindings": bindings,
        "public_feature_access_at": public_access_at,
        "test_public_access": {
            "at": public_access_at,
            "scope": (
                "all 1147 public question/source texts and whitelisted source metadata "
                "solely to derive counts, features and overlaps"
            ),
            "test_outputs_or_correctness_read": False,
        },
        "role_plan_id": original["role_plan"]["id"],
        "features": features,
        "populations": populations,
    }
    if (output / "public_features.json").exists():
        prior = read_json(output / "public_features.json")
        require(
            prior["id"] == digest({k: v for k, v in prior.items() if k != "id"}),
            "prior feature digest mismatch",
        )
        # Reproduction retains the recorded first public-feature access time;
        # every source binding, feature, population and rule must still match.
        feature_value["public_feature_access_at"] = prior["public_feature_access_at"]
        feature_value["test_public_access"] = prior["test_public_access"]
    feature_value["id"] = digest(feature_value)
    # Complete features are published before any downstream score join can start.
    write_once(output / "public_features.json", feature_value)
    analysis = {
        "schema": "v24_public_population_analysis.v1",
        "protocol_id": protocol["id"],
        "public_features_id": feature_value["id"],
        "source_bindings": bindings,
        "scope": protocol["rules"]["scope"],
        **summarize(features, populations),
    }
    analysis["id"] = digest(analysis)
    write_once(output / "population_analysis.json", analysis)
    return {
        "protocol_id": protocol["id"],
        "features_id": feature_value["id"],
        "population_analysis_id": analysis["id"],
        "population_counts": {name: len(keys) for name, keys in populations.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    result = freeze(args.output) if args.freeze_only else run(args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "rules"}, sort_keys=True))
