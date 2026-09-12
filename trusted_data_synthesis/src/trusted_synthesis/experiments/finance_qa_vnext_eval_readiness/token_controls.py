"""One real CPU construction for new evaluation controls only, never training data."""

from ..finance_qa_vnext_catalog_bridge.materials import load_local_tokenizer
from ..finance_qa_vnext_model_execution.representation import encode_original_candidate
from ..finance_qa_vnext_task_build.archive import record, require
from ..qa_reasoning_share_training_preflight import tokenization as assets


def materialize(packages, root, *, loader=load_local_tokenizer):
    eligible = [x for x in packages if x["financial_valid"] and x["complete_first_final_package"]]
    require(
        all(
            x["origin"] == "scripted_evaluation_control"
            and not x["training_eligible"]
            and x["training_samples"] == 0
            for x in packages
        ),
        "tokens.new_scripts_only",
    )
    require(
        len({x["session_id"] for x in packages}) == len(packages), "tokens.unique_script_sessions"
    )
    require(
        all(x["candidates"] and x["candidates"][-1]["response_kind"] == "Final" for x in eligible),
        "tokens.financial_complete_requires_actual_Final_candidates",
    )
    base = {
        "all_script_packages": len(packages),
        "financial_complete_packages": len(eligible),
        "training_samples": 0,
        "old_material_rows_reencoded": 0,
        "model_weight_loads": 0,
        "GPU_runs": 0,
        "maximum_sequence_length": assets.MAX_SEQUENCE_LENGTH,
        "truncation": False,
        "tokenizer_constructions": 0,
        "rows": [],
        "failures": [],
    }
    if not eligible:
        return record("new_eval_token_controls", status="NO_FINANCIAL_COMPLETE_PACKAGES", **base)
    base["tokenizer_constructions"] = 1
    try:
        binding, tokenizer = loader(root)
        require(
            binding["maximum_sequence_length"] == assets.MAX_SEQUENCE_LENGTH == 24576
            and binding["model_max_position_embeddings"] >= 24576,
            "tokens.frozen_model_limits",
        )
        base["tokenizer_binding"] = binding
        for package in eligible:
            for candidate in package["candidates"]:
                try:
                    encoded = encode_original_candidate(
                        candidate, binding, tokenizer, maximum_sequence_length=24576
                    )
                    base["rows"].append(
                        {
                            "package_id": package["id"],
                            "candidate_id": candidate["id"],
                            "representation": encoded,
                        }
                    )
                    if not encoded["consumable_token_representation"]:
                        base["failures"].append(
                            {"candidate_id": candidate["id"], "reason": encoded["reason"]}
                        )
                except (ValueError, TypeError, KeyError, RuntimeError, UnicodeError) as error:
                    base["failures"].append({"candidate_id": candidate["id"], "reason": str(error)})
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, ImportError) as error:
        base["failures"].append({"phase": "local_tokenizer", "reason": str(error)})
    base.update(
        encoded_rows=len(base["rows"]),
        target_tokens=sum(x["representation"]["target_token_count"] for x in base["rows"]),
        sequence_tokens=sum(x["representation"]["sequence_length"] for x in base["rows"]),
        maximum_actual_sequence_length=max(
            (x["representation"]["sequence_length"] for x in base["rows"]), default=0
        ),
    )
    return record(
        "new_eval_token_controls",
        status="PASS_SCRIPTED_REPRESENTATION_ONLY" if not base["failures"] else "FAIL",
        **base,
    )
