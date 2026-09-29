"""Public-only Student representation preflight before the independent new Probe.

API output limits are not Qwen token counts. Initial fit never admits a generated
package: every actual full-history Student row still must fit 24576 without cuts.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from .calibration import now, publish
from .contracts import RunConfig, digest
from .harness import episode_tool_specs, public_initial_messages, system_message
from .planning import task_key, verify_role_plan
from .profiles import public_run_view
from .providers import tokenizer_binding
from .storage import load_public_snapshot, read_json
from .v6_collection import STUDY, bound, require
from .v6_review_revision import original_protocol
from .v7_base_evaluation import load_tokenizer
from .v7_full_probe import OUTPUT as MATERIAL

OUTPUT = STUDY / "audit_revision_20260929/representation_preflight"
STUDENT_CONTEXT = 24576


def validate_material_registration(material):
    """Preserve the v1 registration whose histogram was hashed with integer keys.

    JSON reload stringifies those keys and changes sort order. Rebuild ONLY this
    declared histogram from the actual registered configs; never rewrite the old
    artifact or accept a changed field under a new identity.
    """
    body = {k: v for k, v in material.items() if k != "id"}
    canonical = digest(body)
    if material["id"] == canonical:
        return dict(
            original_id=material["id"],
            canonical_loaded_digest=canonical,
            legacy_integer_histogram_reconstruction=False,
        )
    require(
        material.get("schema") == "finqa_v7_new_full_probe.v1",
        "unexpected material registration version",
    )
    expected = dict(Counter(c["max_new_tokens"] for c in body["configs_by_task"].values()))
    require(
        body["capacity_histogram"] == {str(k): v for k, v in expected.items()},
        "historical capacity histogram differs from actual registered configurations",
    )
    body["capacity_histogram"] = expected
    require(material["id"] == digest(body), "original new-batch registration changed")
    return dict(
        original_id=material["id"],
        canonical_loaded_digest=canonical,
        legacy_integer_histogram_reconstruction=True,
        original_bytes_and_id_not_rewritten=True,
    )


def measure_initial(task, config, tokenizer):
    messages = public_initial_messages(task, config)
    tools = episode_tool_specs(config)
    rendered = tokenizer.apply_chat_template(
        messages, tools=tools, tokenize=False, add_generation_prompt=True
    )
    ids = tokenizer(rendered, add_special_tokens=False, truncation=False, padding=False)[
        "input_ids"
    ]
    require(
        tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        == rendered,
        "initial Student template must preserve public input bytes",
    )
    return dict(
        task_id=task.task_id,
        public_view_sha256=digest(public_run_view(task, config.submission_profile)),
        initial_messages_sha256=digest(messages),
        tools_sha256=digest(tools),
        initial_Student_prompt_tokens=len(ids),
        initial_Student_prompt_sha256=digest(ids),
        API_output_limit=config.max_new_tokens,
        Student_context_limit=STUDENT_CONTEXT,
        initial_prefix_fits=len(ids) + 1 < STUDENT_CONTEXT,
        available_Student_tokens_after_initial_and_EOS=STUDENT_CONTEXT - len(ids) - 1,
        one_response_total_if_token_counts_were_equal=len(ids) + config.max_new_tokens + 1,
        equal_token_count_comparison_is_not_a_bound=True,
        complete_multiturn_package_fit_claimed=False,
    )


def build_preflight(material, tasks, tokenizer):
    historical_identity = validate_material_registration(material)
    require(
        len(tasks) == 1000 and [t.task_id for t in tasks] == material["task_ids"],
        "representation preflight must retain all original1000 tasks",
    )
    rows = []
    for task in tasks:
        cfg = RunConfig.model_validate(material["configs_by_task"][task.task_id])
        require(
            system_message(cfg) == material["public_system"]
            and episode_tool_specs(cfg) == material["public_tools"],
            "frozen public Probe contract changed",
        )
        row = measure_initial(task, cfg, tokenizer)
        require(
            row["public_view_sha256"]
            == material["public_capacity_by_task"][task.task_id]["public_view_sha256"],
            "registered public task view changed",
        )
        rows.append(row)
    token_hash, template_hash = tokenizer_binding(tokenizer)
    long_rows = [r for r in rows if r["API_output_limit"] == 16384]
    failed = [r["task_id"] for r in rows if not r["initial_prefix_fits"]]
    return bound(
        dict(
            schema="v8_public_representation_preflight.v1",
            at=now(),
            original_material_protocol_id=material["id"],
            task_denominator=1000,
            tokenizer_digest=token_hash,
            chat_template_digest=template_hash,
            rows=rows,
            output_cap_histogram={
                str(k): v for k, v in Counter(r["API_output_limit"] for r in rows).items()
            },
            historical_identity=historical_identity,
            long_cap_task_ids=[r["task_id"] for r in long_rows],
            initial_prompt_range=[
                min(r["initial_Student_prompt_tokens"] for r in rows),
                max(r["initial_Student_prompt_tokens"] for r in rows),
            ],
            long_initial_prompt_range=[
                min(r["initial_Student_prompt_tokens"] for r in long_rows),
                max(r["initial_Student_prompt_tokens"] for r in long_rows),
            ]
            if long_rows
            else None,
            initial_prefix_blockers=failed,
            initial_representation_admitted=not failed,
            output_cap_adjustments={},
            public_Probe_contract_changed=False,
            API_and_Student_tokenizers_equated=False,
            private_reference_read=False,
            no_actual_generation_or_training=True,
            whole_generated_package_admitted=False,
            complete_history_policy=dict(
                context_limit=STUDENT_CONTEXT,
                check="each actual full prompt plus original response plus Student EOS",
                no_truncation=True,
                no_error_prefix_removal=True,
                no_short_package_selection=True,
                overlength_joint_valid_package_blocks_training=True,
                maximum_API_allowance_is_not_a_full_history_fit_guarantee=True,
            ),
        )
    )


def register(output=OUTPUT):
    output = Path(output)
    require(not output.exists(), "representation preflight cannot overwrite earlier evidence")
    material = read_json(MATERIAL / "registration/protocol.json")
    original = original_protocol()
    manifest, tasks, lineages = load_public_snapshot(material["original_snapshot"])
    require(manifest["id"] == material["snapshot_id"], "public snapshot changed")
    verify_role_plan(material["role_plan"], tasks, lineages)
    tasks = [t for t in tasks if material["role_plan"]["assignments"][task_key(t)] == "sft"]
    tokenizer = load_tokenizer(original["assets"])
    result = build_preflight(material, tasks, tokenizer)
    result.pop("id")
    result.update(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    result = bound(result)
    publish(output, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    result = register(args.output)
    print(
        {
            k: result[k]
            for k in (
                "id",
                "initial_representation_admitted",
                "task_denominator",
                "initial_prompt_range",
                "long_initial_prompt_range",
                "output_cap_histogram",
                "whole_generated_package_admitted",
            )
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
