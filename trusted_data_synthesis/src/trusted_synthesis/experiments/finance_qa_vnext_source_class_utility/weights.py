"""One immutable physical row view; arms differ only in exact loss coefficients."""

from collections import Counter
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.source import (
    content_identity,
)

from .plan import (
    CONDITIONS,
    TASKS,
    TRAIN_SYSTEM,
    encode,
    package_mass,
    read_json,
    record,
    reference,
    require,
    sha,
)


def bound(root, ref, *, binary=False):
    relative = Path(ref["path"])
    require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and relative.parts[:2] == ("trusted_data_synthesis", "artifacts"),
        "view.exact_artifact_reference",
    )
    require(
        reference(root, relative) == {k: ref[k] for k in ("path", "bytes", "sha256")},
        "view.bound_original_bytes",
    )
    raw = (Path(root) / relative).read_bytes()
    if binary:
        return raw
    value = read_json(Path(root) / relative)
    content_identity(value, "view.bound_content_identity")
    if ref.get("id") is not None:
        require(value["id"] == ref["id"], "view.bound_record_ID")
    return value


def validate_arrays(token, candidate, target):
    content_identity(token, "view.token_identity")
    content_identity(candidate, "view.candidate_identity")
    require(
        candidate["id"] == token["candidate_id"]
        and candidate["target_response"].encode() == target
        and token["raw_response_sha256"] == candidate["raw_response_sha256"] == sha(target),
        "view.original_text_candidate_token_join",
    )
    for key in (
        "session_label",
        "task_key",
        "response_index",
        "response_kind",
        "population",
        "source_closeout_id",
        "request_sha256",
        "response_projection_sha256",
    ):
        require(candidate[key] == token[key], "view.same_original_interaction")
    require(candidate["population"] in {"N", "T"}, "view.no_E_material")
    if candidate["population"] == "N":
        require(
            candidate["input_messages"][0]["content"] == TRAIN_SYSTEM,
            "view.original_N_instruction_not_deleted",
        )
    size, start, end = (
        token["sequence_length"],
        token["target_token_start"],
        token["target_token_end"],
    )
    require(
        token["consumable_token_representation"]
        and token["tokenrepresentation_status"] == "fit"
        and not token["truncated"]
        and 0 < size <= 32768
        and 0 < start < end < size
        and token["target_token_count"] == end - start
        and token["causal_shift"] == 1,
        "view.complete_original_token_interval",
    )
    require(
        all(
            isinstance(token[k], list) and len(token[k]) == size
            for k in ("input_ids", "attention_mask", "target_mask", "labels")
        ),
        "view.complete_arrays",
    )
    mask = [int(start <= i < end) for i in range(size)]
    ids = token["input_ids"]
    require(
        token["target_mask"] == mask
        and token["attention_mask"] == [1] * size
        and all(type(v) is int and v >= 0 for v in ids)
        and token["labels"] == [v if mask[i] else -100 for i, v in enumerate(ids)]
        and ids[end:] == [151645, 198]
        and token["labels"][0] == -100,
        "view.target_only_mask_and_causal_shift",
    )


def build_view(packages, rows):
    packages = [dict(p) for p in packages]
    rows = [dict(row, row_index=i) for i, row in enumerate(rows)]
    for package in packages:
        label = package["session_label"]
        own = [r for r in rows if r["session_label"] == label]
        length = sum(r["target_token_count"] for r in own)
        require(length > 0, "view.nonempty_whole_package")
        package.update(
            target_token_count=length,
            row_indices=[r["row_index"] for r in own],
            mu="1/6",
            kappa="1/3",
            mass={
                arm: str(package_mass(arm, package["task_key"], package["route"]))
                for arm in CONDITIONS
            },
        )
        for row in own:
            row["package_target_token_count"] = length
            row["coefficient"] = {
                arm: str(Fraction(package["mass"][arm]) / length) for arm in CONDITIONS
            }
    view = record(
        "source_class_weight_view",
        packages=packages,
        rows=rows,
        totals=dict(
            packages=len(packages),
            rows=len(rows),
            target_tokens_per_pass=sum(r["target_token_count"] for r in rows),
            sequence_tokens_per_pass=sum(r["sequence_length"] for r in rows),
        ),
        physical_row_reference_sha256=sha(
            encode([{k: v for k, v in row.items() if k != "coefficient"} for row in rows])
        ),
        original_prefixes_targets_arrays_and_masks_unchanged=True,
        same_physical_data_in_all_arms=True,
        per_package_target_mean_loss=True,
        no_row_or_global_token_mean_after_weighting=True,
        only_X3C_D_A_class_mass_changes=True,
        no_resampling=True,
    )
    validate_view(view)
    return view


def validate_view(view):
    content_identity(view, "view.content_identity")
    packages, rows = view["packages"], view["rows"]
    require(
        len(packages) == 21 and len({p["session_label"] for p in packages}) == 21,
        "view.fixed_21_unique_packages",
    )
    require(
        Counter(p["task_key"] for p in packages) == {k: 6 if k == "X3C" else 3 for k in TASKS},
        "view.fixed_six_task_support",
    )
    require(
        Counter((p["task_key"], p["route"]) for p in packages)
        == {
            **{(k, "control"): 3 for k in ("G1", "G2", "F1")},
            ("X1", "D"): 3,
            ("X2", "D"): 3,
            ("X3C", "D"): 3,
            ("X3C", "A"): 3,
        },
        "view.fixed_class_internal_kernel",
    )
    require(
        [r["row_index"] for r in rows] == list(range(len(rows)))
        and len({r["token_reference"]["path"] for r in rows}) == len(rows),
        "view.fixed_unique_physical_rows",
    )
    require(
        view["physical_row_reference_sha256"]
        == sha(encode([{k: v for k, v in row.items() if k != "coefficient"} for row in rows])),
        "view.arm_independent_physical_identity",
    )
    expected_totals = dict(
        packages=21,
        rows=len(rows),
        target_tokens_per_pass=sum(r["target_token_count"] for r in rows),
        sequence_tokens_per_pass=sum(r["sequence_length"] for r in rows),
    )
    require(view["totals"] == expected_totals, "view.actual_not_inherited_token_budget")
    for package in packages:
        own = [r for r in rows if r["session_label"] == package["session_label"]]
        length = sum(r["target_token_count"] for r in own)
        require(
            length == package["target_token_count"] > 0
            and package["kappa"] == "1/3"
            and package["mu"] == "1/6"
            and package["row_indices"] == [r["row_index"] for r in own],
            "view.whole_package_count_and_kernel",
        )
        for arm in CONDITIONS:
            mass = package_mass(arm, package["task_key"], package["route"])
            require(Fraction(package["mass"][arm]) == mass, "view.exact_package_mass")
            require(
                all(
                    Fraction(r["coefficient"][arm]) == mass / length
                    and r["package_target_token_count"] == length
                    for r in own
                ),
                "view.exact_whole_package_loss_coefficients",
            )
    for arm in CONDITIONS:
        require(sum(Fraction(p["mass"][arm]) for p in packages) == 1, "view.unit_total_mass")
        for key in TASKS:
            require(
                sum(Fraction(p["mass"][arm]) for p in packages if p["task_key"] == key)
                == Fraction(1, 6),
                "view.fixed_task_marginal",
            )


def load_rows(root, view):
    validate_view(view)
    result = []
    for row in view["rows"]:
        token = bound(root, row["token_reference"])
        candidate = bound(root, row["candidate_reference"])
        raw = bound(root, row["target_raw_reference"], binary=True)
        validate_arrays(token, candidate, raw)
        require(
            row["sequence_length"] == token["sequence_length"]
            and row["target_token_count"] == token["target_token_count"],
            "view.registered_actual_token_counts",
        )
        start, end = token["target_token_start"], token["target_token_end"]
        result.append(
            {
                **row,
                "input_ids": token["input_ids"],
                "attention_mask": token["attention_mask"],
                "target_ids": token["labels"][start:end],
                "logit_positions": list(range(start - 1, end - 1)),
            }
        )
    return result
