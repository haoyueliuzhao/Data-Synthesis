"""Exact P/Q masses referencing the eighteen existing immutable token packages.

This is a new loss view, not a new materialization, tokenizer pass, qualification
or nineteen-pair measurement. Original text, arrays, masks and source metadata
remain in source files; only task/class/package/token coefficients are new.
"""

import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from .plan import SOURCE, TASKS, encode, record, require, sha

MATERIALIZATION = SOURCE + "/closeout/materialization"
INDEX_PATH = MATERIALIZATION + "/index.json"
INDEX_ID = (
    "new_support_materialization_index:"
    "ecc1ed467670b077ae929903a300a3988166ba62d312189dedd364aa592fee6c"
)
INDEX_SHA256 = "7e8ccf83f765405c3b168de81fa125bf5c9c73660bac4f6fa5015e4620478f2d"
MEASUREMENT_PATH = SOURCE + "/closeout/measurement.json"
MEASUREMENT_SHA256 = "95e7aec2da65f70223fc62b9c0b555f1c7595dc44fc1bab0aed5de7b460986b5"
COUNTS = {"G1": 3, "G2": 3, "F1": 3, "F2": 4, "L1": 3, "L2": 2}
REPLICATES = {
    "G1": (1, 2, 3),
    "G2": (1, 2, 3),
    "F1": (2, 3, 4),
    "F2": (1, 2, 3, 4),
    "L1": (1, 3, 4),
    "L2": (1, 2),
}
BALANCE_LABELS = ("T_L1_01", "T_L1_04")
MOVEMENT_LABEL = "T_L1_03"
BALANCE_CLASS = (
    "new_open_support_class:c51179c306d49acf5b7c357ec7bd357f2d311ce1f6237292a1c24367d2fa3355"
)
MOVEMENT_CLASS = (
    "new_open_support_class:03772e4dc63e24d7887aa293417f2df4debcb0dd62ab27ca852ef783dab41976"
)
ARMS = ("P", "Q")
ARRAYS = ("input_ids", "attention_mask", "labels", "target_mask")


def fraction(value):
    """Interpret serialized exact coefficients without silently accepting NaN."""
    require(
        isinstance(value, (str, int, Fraction)) and not isinstance(value, bool),
        "weights.exact_fraction",
    )
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError):
        raise ValueError("weights.exact_fraction") from None


def _identity(value, code):
    require(isinstance(value, dict) and isinstance(value.get("id"), str), code)
    kind, separator, digest = value["id"].partition(":")
    require(
        bool(kind)
        and separator == ":"
        and len(digest) == 64
        and value["id"] == kind + ":" + sha(encode({k: v for k, v in value.items() if k != "id"})),
        code,
    )


def _read(root, relative, *, as_json=True, expected_sha=None):
    relative = Path(relative)
    require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and relative.is_relative_to(Path(SOURCE)),
        "weights.original_source_path",
    )
    path = Path(root) / relative
    require(
        path.is_file()
        and not path.is_symlink()
        and path.resolve().is_relative_to((Path(root) / SOURCE).resolve()),
        "weights.original_regular_file",
    )
    raw = path.read_bytes()
    require(expected_sha is None or sha(raw) == expected_sha, "weights.frozen_source_bytes")
    value = json.loads(raw) if as_json else raw
    if as_json:
        _identity(value, "weights.original_record_identity")
    return value, {
        "path": relative.as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
        "id": value["id"] if as_json else None,
    }


def _bound(root, reference, *, as_json=True):
    value, current = _read(root, reference["path"], as_json=as_json)
    require(current == reference, "weights.bound_reference_changed")
    return value


def _token(token, candidate, target_raw, original_row, binding_id, policy_id):
    require(
        token["id"] == original_row["representation_id"]
        and candidate["id"] == token["candidate_id"] == original_row["candidate_id"]
        and token["tokenizer_binding_id"] == binding_id
        and token["representation_policy_id"] == policy_id,
        "weights.original_row_join",
    )
    for key in ("population", "session_label", "task_key", "response_index", "response_kind"):
        require(token[key] == candidate[key] == original_row[key], "weights.original_row_metadata")
    require(
        token["population"] == "T"
        and token["raw_response_sha256"] == candidate["raw_response_sha256"] == sha(target_raw)
        and candidate["target_response"].encode("utf-8") == target_raw
        and token["target_raw_byte_count"] == len(target_raw)
        and token["request_sha256"] == candidate["request_sha256"]
        and token["response_projection_sha256"] == candidate["response_projection_sha256"],
        "weights.original_text_target_metadata",
    )
    size, start, end = (
        token["sequence_length"],
        token["target_token_start"],
        token["target_token_end"],
    )
    require(
        token["consumable_token_representation"] is True
        and token["tokenrepresentation_status"] == "fit"
        and token["truncated"] is False
        and type(size) is int
        and 0 < size <= token["maximum_sequence_length"] == 32_768
        and type(start) is int
        and type(end) is int
        and 0 < start < end < size
        and token["target_token_count"] == original_row["target_token_count"] == end - start
        and token["prompt_token_count"] == original_row["prompt_token_count"] == start
        and size == original_row["sequence_length"]
        and token["suffix_token_count"] == size - end == 2
        and token["causal_shift"] == 1
        and token["causal_target_token_start"] == start - 1
        and token["causal_target_token_end"] == end - 1,
        "weights.original_causal_target_interval",
    )
    require(
        all(isinstance(token[name], list) and len(token[name]) == size for name in ARRAYS),
        "weights.original_array_shapes",
    )
    ids, labels, mask = token["input_ids"], token["labels"], token["target_mask"]
    require(all(type(value) is int and value >= 0 for value in ids), "weights.input_token_ids")
    expected_mask = [int(start <= i < end) for i in range(size)]
    require(
        mask == expected_mask
        and labels == [value if mask[i] else -100 for i, value in enumerate(ids)]
        and token["attention_mask"] == [1] * size
        and ids[end:] == [151645, 198]
        and labels[0] == -100,
        "weights.original_target_only_labels",
    )


def _groups(packages):
    groups = defaultdict(list)
    for package in packages:
        groups[(package["task_key"], package["class_id"])].append(package)
    return groups


def _masses(packages):
    groups, result = _groups(packages), {}
    for arm in ARMS:
        conditional, class_mass, task_mass, package_mass = {}, {}, {}, {}
        for task in TASKS:
            conditional[task], class_mass[task] = {}, {}
            for (group_task, class_id), members in groups.items():
                if group_task != task:
                    continue
                probability = Fraction(len(members), COUNTS[task])
                if arm == "Q" and task == "L1":
                    probability = Fraction(1, 2)
                conditional[task][class_id] = str(probability)
                class_mass[task][class_id] = str(Fraction(1, 6) * probability)
                for package in members:
                    package_mass[package["session_label"]] = str(
                        Fraction(1, 6) * probability / len(members)
                    )
            task_mass[task] = str(sum((fraction(v) for v in class_mass[task].values()), Fraction()))
        result[arm] = {
            "conditional_class_probabilities": conditional,
            "class_masses": class_mass,
            "task_masses": task_mass,
            "package_masses": package_mass,
            "total_mass": str(sum((fraction(v) for v in package_mass.values()), Fraction())),
        }
    return result


def validate_weights(view):
    """Check exact intervention mathematics, including rehashed coefficient mutations."""
    _identity(view, "weights.view_identity")
    packages, rows = view["packages"], view["rows"]
    require(view["source_dataset_id"] == INDEX_ID, "weights.original_dataset_identity")
    require(
        view["shared_representation_reference_id"]
        == sha(
            encode(
                [{key: value for key, value in row.items() if key != "coefficient"} for row in rows]
            )
        ),
        "weights.shared_representation_reference",
    )
    expected_labels = {f"T_{task}_{rep:02d}" for task, reps in REPLICATES.items() for rep in reps}
    by_label = {package["session_label"]: package for package in packages}
    require(
        len(packages) == len(by_label) == 18
        and set(by_label) == expected_labels
        and Counter(package["task_key"] for package in packages) == COUNTS,
        "weights.fixed_eighteen_package_population",
    )
    groups = _groups(packages)
    for task in TASKS:
        require(
            sum(key[0] == task for key in groups) == (2 if task == "L1" else 1),
            "weights.fixed_class_counts",
        )
    require(
        all(by_label[label]["class_id"] == BALANCE_CLASS for label in BALANCE_LABELS)
        and by_label[MOVEMENT_LABEL]["class_id"] == MOVEMENT_CLASS,
        "weights.frozen_L1_class_assignment",
    )
    require(
        len(rows) == 36 and [row["row_index"] for row in rows] == list(range(36)),
        "weights.fixed_row_order",
    )
    require(
        len({row["token_reference"]["id"] for row in rows}) == 36, "weights.no_duplicate_token_rows"
    )
    require(view["views"] == _masses(packages), "weights.exact_P_Q_class_intervention")
    for arm in ARMS:
        require(
            view["views"][arm]["total_mass"] == "1"
            and set(view["views"][arm]["task_masses"].values()) == {"1/6"},
            "weights.fixed_task_and_total_mass",
        )
    changed = []
    for label, package in by_label.items():
        own_rows = [row for row in rows if row["session_label"] == label]
        total = sum(row["target_token_count"] for row in own_rows)
        require(
            len(own_rows) == 2
            and [row["response_index"] for row in own_rows] == [0, 1]
            and package["target_token_count"] == total > 0
            and package["mu"] == "1/6"
            and package["row_indices"] == [row["row_index"] for row in own_rows]
            and package["kappa"]
            == str(Fraction(1, len(groups[(package["task_key"], package["class_id"])]))),
            "weights.fixed_class_internal_kernel_and_package_length",
        )
        for row in own_rows:
            require(
                all(
                    row[key] == row["original_index_row"][key]
                    for key in (
                        "session_label",
                        "task_key",
                        "class_id",
                        "package_id",
                        "response_index",
                        "response_kind",
                        "sequence_length",
                        "target_token_count",
                    )
                )
                and row["package_target_token_count"] == total,
                "weights.original_view_row_metadata",
            )
            require(
                row["class_id"] == package["class_id"] and row["task_key"] == package["task_key"],
                "weights.row_package_class_join",
            )
            for arm in ARMS:
                mass = view["views"][arm]["package_masses"][label]
                require(package["mass"][arm] == mass, "weights.package_mass")
                require(
                    row["coefficient"][arm] == str(fraction(mass) / total),
                    "weights.whole_package_target_token_mean",
                )
        if package["mass"]["P"] != package["mass"]["Q"]:
            changed.append(label)
    require(
        set(changed) == {*BALANCE_LABELS, MOVEMENT_LABEL}, "weights.only_three_L1_packages_changed"
    )
    require(
        sum(row["target_token_count"] for row in rows) == 4793
        and sum(row["sequence_length"] for row in rows) == 232603,
        "weights.same_physical_token_budget",
    )
    return {
        "all_task_masses": "1/6",
        "total_mass_P": "1",
        "total_mass_Q": "1",
        "changed_package_labels": sorted(changed),
        "package_count": 18,
        "row_count": 36,
        "target_tokens_per_pass": 4793,
        "sequence_tokens_per_pass": 232603,
        "identity": "L_Q-L_P=(ell_T_L1_03-(ell_T_L1_01+ell_T_L1_04)/2)/36",
    }


def build(root):
    """Construct references and exact masses; never tokenize, regenerate or reclassify."""
    index, index_ref = _read(root, INDEX_PATH, expected_sha=INDEX_SHA256)
    measurement, measurement_ref = _read(root, MEASUREMENT_PATH, expected_sha=MEASUREMENT_SHA256)
    require(index["id"] == INDEX_ID, "weights.fixed_original_dataset")
    require(
        index["valid_package_count"] == 18 and index["positive_row_count"] == 36,
        "weights.original_counts",
    )
    binding, binding_ref = _read(root, MATERIALIZATION + "/tokenizer_binding.json")
    policy, policy_ref = _read(root, MATERIALIZATION + "/representation_policy.json")
    require(
        policy["maximum_sequence_length"] == 32768 and policy["truncation"] is False,
        "weights.original_representation_policy",
    )
    packages = []
    for summary in index["packages"]:
        label = summary["session_label"]
        package, reference = _read(root, MATERIALIZATION + f"/packages/{label}.json")
        require(
            all(package[key] == value for key, value in summary.items())
            and package["class_id"] == measurement["session_class_ids"][label]
            and package["behavior_mapping_status"] == "MAPPED"
            and package["whole_package_token_consumable"] is True
            and package["package_weight"]
            is package["class_weight"]
            is package["task_weight"]
            is None,
            "weights.existing_package_and_assignment",
        )
        own_rows = [row for row in index["rows"] if row["session_label"] == label]
        require(
            package["positive_candidate_ids"] == [row["candidate_id"] for row in own_rows]
            and package["token_representation_ids"]
            == [row["representation_id"] for row in own_rows]
            and package["positive_row_paths"] == [row["path_prefix"] for row in own_rows]
            and all(row["package_id"] == package["id"] for row in own_rows),
            "weights.original_package_row_membership",
        )
        packages.append(
            {
                "session_label": label,
                "task_key": package["task_key"],
                "class_id": package["class_id"],
                "package_id": package["id"],
                "package_reference": reference,
                "target_token_count": sum(row["target_token_count"] for row in own_rows),
                "source_closeout_id": package["source_closeout_id"],
                "behavior_projection_id": package["behavior_projection_id"],
            }
        )
    groups, views = _groups(packages), _masses(packages)
    by_label, rows = {package["session_label"]: package for package in packages}, []
    for position, original in enumerate(index["rows"]):
        prefix = MATERIALIZATION + "/" + original["path_prefix"]
        token, token_ref = _read(root, prefix + ".tokens.json")
        candidate, candidate_ref = _read(root, prefix + ".candidate.json")
        target_raw, target_ref = _read(root, prefix + ".target.raw", as_json=False)
        _token(token, candidate, target_raw, original, binding["id"], policy["id"])
        package = by_label[original["session_label"]]
        rows.append(
            {
                "row_index": position,
                "session_label": original["session_label"],
                "task_key": original["task_key"],
                "class_id": original["class_id"],
                "package_id": original["package_id"],
                "response_index": original["response_index"],
                "response_kind": original["response_kind"],
                "target_token_count": token["target_token_count"],
                "sequence_length": token["sequence_length"],
                "package_target_token_count": package["target_token_count"],
                "token_reference": token_ref,
                "candidate_reference": candidate_ref,
                "target_raw_reference": target_ref,
                "original_index_row": original,
                "coefficient": {
                    arm: str(
                        fraction(views[arm]["package_masses"][package["session_label"]])
                        / package["target_token_count"]
                    )
                    for arm in ARMS
                },
            }
        )
    for package in packages:
        label = package["session_label"]
        package.update(
            kappa=str(Fraction(1, len(groups[(package["task_key"], package["class_id"])]))),
            mu="1/6",
            mass={arm: views[arm]["package_masses"][label] for arm in ARMS},
            row_indices=[row["row_index"] for row in rows if row["session_label"] == label],
        )
    view = record(
        "pq_weight_views",
        source_dataset_id=index["id"],
        source_references={
            "index": index_ref,
            "measurement": measurement_ref,
            "tokenizer_binding": binding_ref,
            "representation_policy": policy_ref,
        },
        shared_representation_reference_id=sha(
            encode(
                [{key: value for key, value in row.items() if key != "coefficient"} for row in rows]
            )
        ),
        packages=packages,
        rows=rows,
        views=views,
        totals={
            "packages": 18,
            "rows": 36,
            "target_tokens_per_pass": 4793,
            "sequence_tokens_per_pass": 232603,
        },
        package_loss=(
            "sum all original positive target-token NLL in the whole package / "
            "its total target tokens"
        ),
        row_loss="sum original target-token NLL * package_mass / package_target_token_count",
        global_or_row_mean_after_weighting=False,
        causal_label_shift=1,
        original_labels_masks_token_ids_and_text_unchanged=True,
        original_arrays_retokenized=False,
        old_qualification_or_pairs_recomputed=False,
        original_failure_and_unknown_packages_excluded_without_promotion=True,
        fixed_mu_and_kappa=True,
        only_L1_class_mass_changed=True,
        Q_is_diagnostic_not_an_optimized_distribution=True,
    )
    validate_weights(view)
    return view


def load_rows(root, view):
    """Read original arrays once for a run; preserve originals and add only view metadata."""
    validate_weights(view)
    references = view["source_references"]
    index = _bound(root, references["index"])
    require(
        references["index"]["sha256"] == INDEX_SHA256 and index["id"] == INDEX_ID,
        "weights.original_index_authority",
    )
    measurement = _bound(root, references["measurement"])
    require(
        references["measurement"]["sha256"] == MEASUREMENT_SHA256,
        "weights.original_measurement_authority",
    )
    binding, policy = (
        _bound(root, references["tokenizer_binding"]),
        _bound(root, references["representation_policy"]),
    )
    packages = {package["session_label"]: package for package in view["packages"]}
    for package in packages.values():
        original = _bound(root, package["package_reference"])
        require(
            original["id"] == package["package_id"]
            and original["class_id"]
            == package["class_id"]
            == measurement["session_class_ids"][package["session_label"]],
            "weights.original_package_class_authority",
        )
    loaded = []
    for row in view["rows"]:
        require(
            row["original_index_row"] == index["rows"][row["row_index"]],
            "weights.original_shared_row_order",
        )
        token = _bound(root, row["token_reference"])
        candidate = _bound(root, row["candidate_reference"])
        target = _bound(root, row["target_raw_reference"], as_json=False)
        _token(token, candidate, target, row["original_index_row"], binding["id"], policy["id"])
        require(
            row["target_token_count"] == token["target_token_count"]
            and row["sequence_length"] == token["sequence_length"],
            "weights.loaded_row_counts",
        )
        positions = [index for index, value in enumerate(token["labels"]) if value != -100]
        loaded.append(
            {
                **row,
                **{name: token[name] for name in ARRAYS},
                "target_positions": positions,
                "logit_positions": [position - 1 for position in positions],
                "target_ids": [token["labels"][position] for position in positions],
                "token_record": token,
                "candidate": candidate,
            }
        )
    return loaded
