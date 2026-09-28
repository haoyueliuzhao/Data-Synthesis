"""Independently registered structured-action Probe batch, never an old-slot retry."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import probe_collection as controller
from .calibration import CACHE, ROOT, now, publish
from .contracts import RunConfig, digest
from .probe_budget import ProbePriceSheet
from .probe_inventory import register_inventory
from .probe_scope import validate_conditional_scope
from .qualification import qualification_rules
from .state_mapping import mapper_rules
from .storage import read_json, runtime_binding
from .training_policy import conditional_training_interface_policy

FOLLOWUP = CACHE / "structured_probe_followup_01"
PREVIOUS = CACHE / "finqa_conditional_probe_inventory_01"
OUTPUT = FOLLOWUP / "structured_inventory_01"
DIAGNOSTIC = FOLLOWUP / "legacy_output_diagnostic_01"
OFFICIAL = FOLLOWUP / "official_docs_01/snapshot.json"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/fcb61576-057e-40bc-b0e3-81156207f5f8/已粘贴的文本.txt"
)
NEW_HARNESS = "bigfinance-derived-vtdo-v4"
NEW_PROFILE = "finqa_program_v3_structured"
BUDGET = dict(hard_cap_microcny=100_000_000, warning_microcny=80_000_000, request_cap=42_240)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _bound(value, field="id", prefix=""):
    if value.get(field) != prefix + digest({k: v for k, v in value.items() if k != field}):
        raise ValueError("source content identity mismatch: " + field)


def continued_scope(previous, rules, mapper):
    """Keep the identical old static cohort; new execution binding, no reselection."""
    old = previous["conditional_scope"]
    validate_conditional_scope(old, old["qualification_rule_id"], old["mapper_rule_id"])
    if len(old["task_ids"]) != 165 or old["mapper_rule_id"] != mapper["id"]:
        raise ValueError("retain the same 165 tasks and Mapper")
    body = copy.deepcopy(old)
    body.pop("scope_id")
    body.update(
        qualification_rule_id=rules["id"],
        static_qualification_rule_id=old["qualification_rule_id"],
        static_selection_reused_from_scope_id=old["scope_id"],
        no_static_or_outcome_based_reselection=True,
        new_execution_contract_is_not_new_financial_semantics=True,
    )
    value = {**body, "scope_id": "finqa_conditional_scope:" + digest(body)}
    return validate_conditional_scope(value, rules["id"], mapper["id"])


def financial_semantics_binding(previous):
    """Bind unchanged proof helpers and decision logic; replay wiring is versioned."""
    relative = "trusted_data_synthesis/src/trusted_synthesis/finance_research/qualification.py"
    old = subprocess.check_output(
        ["git", "show", previous["source_commit"] + ":" + relative], cwd=ROOT, text=True
    )
    current = (ROOT / relative).read_text()

    def helpers(source):
        return {
            node.name: digest(ast.dump(node, include_attributes=False))
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef)
            and node.name not in {"qualification_rules", "qualify_episode", "_replay_episode"}
        }

    marker = "    state_id, verdict, reason = "
    if helpers(old) != helpers(current) or old.partition(marker)[2] != current.partition(marker)[2]:
        raise ValueError("this batch cannot modify source, DAG, units, Final or decision logic")
    binding = runtime_binding()
    for name in ("state_mapping.py", "native_metrics.py"):
        if binding[name] != previous["runtime_binding"][name]:
            raise ValueError("do not change Mapper or native metric logic")
    return dict(
        helper_AST_sha256=helpers(current),
        decision_tail_sha256=hashlib.sha256(current.partition(marker)[2].encode()).hexdigest(),
        unchanged_files={name: binding[name] for name in ("state_mapping.py", "native_metrics.py")},
        permitted_changes=[
            "explicit structured output protocol",
            "shared live/replay context wiring",
        ],
    )


def checked_diagnostic():
    complete = read_json(DIAGNOSTIC / "complete/record.json")
    protocol = read_json(DIAGNOSTIC / "protocol.json")
    summary = read_json(DIAGNOSTIC / "results/summary.json")
    _bound(complete, prefix="finqa_legacy_output_diagnostic_complete:")
    _bound(protocol, prefix="finqa_legacy_output_diagnostic:")
    _bound(summary, prefix="finqa_legacy_output_summary:")
    if (
        not complete["complete"]
        or not summary["complete"]
        or summary["denominator"] != 1320
        or complete["protocol_id"] != protocol["id"]
        or complete["summary_id"] != summary["id"]
        or complete["summary_sha256"] != _sha(DIAGNOSTIC / "results/summary.json")
    ):
        raise ValueError("the bounded old-inventory diagnostic must complete first")
    return dict(
        path=str(DIAGNOSTIC),
        protocol_id=protocol["id"],
        summary_id=summary["id"],
        completion_sha256=_sha(DIAGNOSTIC / "complete/record.json"),
    )


def build_plan(*, source_commit, authorized_CNY, official_path=OFFICIAL):
    if authorized_CNY != 100:
        raise ValueError(
            "explicit new-purpose 100 CNY authorization required; no inherited balance"
        )
    previous = read_json(PREVIOUS / "protocol.json")
    old_inventory = read_json(PREVIOUS / "inventory_complete/record.json")
    _bound(previous)
    _bound(old_inventory, "frozen_inventory_id", "finqa_frozen_probe_support:")
    if old_inventory["inventory_id"] != previous["inventory"]["inventory_id"]:
        raise ValueError("previous frozen inventory binding mismatch")
    diagnostic = checked_diagnostic()
    semantic_binding = financial_semantics_binding(previous)
    rules, mapper = qualification_rules(harness_id=NEW_HARNESS), mapper_rules()
    rule_body = {
        k: v
        for k, v in rules.items()
        if k not in {"id", "previous_financial_rule_id", "execution_protocol_binding"}
    }
    if rule_body != {k: v for k, v in previous["qualification_rules"].items() if k != "id"}:
        raise ValueError("the financial qualification declaration cannot change")
    scope = continued_scope(previous, rules, mapper)
    official_path = Path(official_path)
    official = read_json(official_path)
    checked = datetime.fromisoformat(official["checked_at_utc"])
    age = (datetime.now(timezone.utc) - checked).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError("bind a newly checked official price sheet, not historical spending")
    for document in official["documents"]:
        if _sha(official_path.parent / (document["name"] + ".html")) != document["sha256"]:
            raise ValueError("official document bytes changed")
    peak = official["CNY_per_million_tokens"]["peak"]
    price = ProbePriceSheet(
        input_hit_cny_per_million=peak["input_cache_hit"],
        input_miss_cny_per_million=peak["input_cache_miss"],
        output_cny_per_million=peak["output"],
        context_input_token_ceiling=1048576,
        official_max_output_tokens=393216,
        source_url="https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
        checked_at_utc=official["checked_at_utc"],
        source_sha256=_sha(official_path),
    )
    config = RunConfig(
        harness_id=NEW_HARNESS,
        submission_profile=NEW_PROFILE,
        role="sft",
        temperature=1,
        max_steps=32,
        max_new_tokens=2048,
        context_limit=1048576,
    )
    policy = copy.deepcopy(previous["collection_policy"])
    policy.pop("id")
    policy.update(
        hard_cap_CNY=100,
        warning_CNY=80,
        max_episodes=1320,
        max_requests=42240,
        structured_public_action_language=True,
        preserve_noncompliant_outputs=True,
        no_old_packages_or_sealed_successes_imported=True,
        no_additional_paid_pilots_or_prompt_search=True,
    )
    policy["id"] = "finqa_probe_collection:" + digest(policy)
    inventory = register_inventory(
        task_ids=scope["task_ids"],
        source_manifest_sha256=scope["source_manifest_sha256"],
        qualification_rule_id=rules["id"],
        mapper_rule_id=mapper["id"],
        collection_policy_id=policy["id"],
        slot_config=config,
        conditional_scope=scope,
    )
    order = {task: index for index, task in enumerate(scope["task_ids"])}
    proposal = conditional_training_interface_policy(scope)
    proposal.pop("policy_id")
    proposal["frozen_environment"].update(harness_id=NEW_HARNESS, submission_profile=NEW_PROFILE)
    proposal["probe"].update(spending_warning_CNY="80", hard_cap_CNY="100")
    proposal["training_comparison_proposal_not_run_registration"].update(
        common_static_prefix_steps_per_seed=165,
        total_steps_per_final_model=330,
        branch_suffix_steps_per_arm=165,
        physical_SFT_steps_three_seeds=1485,
        effective_six_model_training_history_steps=1980,
        submission_profile=NEW_PROFILE,
        training_dose_status="conditional proposal only: 165 tasks, 5 per step, 10 epochs",
        actual_full_support_encoding_and_power_registration_required=True,
        D_pi_zero_forbids_a_distribution_optimization_comparison=True,
        nontrivial_support_is_not_evidence_of_statistical_power=True,
    )
    proposal["policy_id"] = "finance_training_interface:" + digest(proposal)
    plan = dict(
        schema="finqa_structured_public_action_collection.v1",
        at=now(),
        authorization="参照审计修订并开展后续实验；独立新批次100元硬上限确认",
        audit=dict(path=str(AUDIT), sha256=_sha(AUDIT)),
        source_commit=source_commit,
        runtime_binding=runtime_binding(),
        previous_protocol_id=previous["id"],
        previous_inventory_root=str(PREVIOUS),
        previous_inventory_complete_sha256=_sha(PREVIOUS / "inventory_complete/record.json"),
        new_batch_not_replacement_or_topup=True,
        old_labels_or_trajectories_modified=False,
        legacy_diagnostic=diagnostic,
        financial_semantics_binding=semantic_binding,
        original_candidate_denominator=1000,
        original_slot_denominator=8000,
        original_1000_training_admitted=False,
        conditional_scope=scope,
        active_task_denominator=165,
        active_slot_denominator=1320,
        snapshot=previous["snapshot"],
        snapshot_id=previous["snapshot_id"],
        role_plan=previous["role_plan"],
        task_ids=scope["task_ids"],
        inventory=inventory,
        launch_order=[
            s["slot_id"]
            for s in sorted(
                inventory["slots"], key=lambda s: (s["slot_index"], order[s["task_id"]])
            )
        ],
        qualification_rules=rules,
        mapper_rules=mapper,
        collection_policy=policy,
        budget_limits=copy.deepcopy(BUDGET),
        price_sheet=asdict(price),
        old_spending_CNY="6.684336",
        old_spending_is_not_new_budget_authority=True,
        official_snapshot=dict(path=str(official_path), sha256=_sha(official_path)),
        future_training_proposal=proposal,
        automatic_training_authorized=False,
        qualifications_only_after_all_registered_slots_settled=True,
        task_deletion_or_probability_renormalization_allowed=False,
        reporting=dict(
            qualified_slots_renamed_to_assessed_slots=True,
            D_pi_and_M_flex_required=True,
            state_samples_and_API_tokens_required=True,
            Student_tokens_require_separate_actual_offline_encoding=True,
            old_new_difference_is_joint_protocol_development_observation=True,
        ),
    )
    plan["id"] = digest(plan)
    return plan


def register(output, *, authorized_CNY):
    if authorized_CNY != 100:
        raise ValueError("explicit new-purpose 100 CNY authorization required")
    output = Path(output).resolve()
    if output.exists():
        return controller.checked_plan(output)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        if path.read_bytes() != subprocess.check_output(
            ["git", "show", head + ":" + str(path.relative_to(ROOT))], cwd=ROOT
        ):
            raise ValueError("commit the new fixed protocol before paid registration")
    plan = build_plan(source_commit=head, authorized_CNY=authorized_CNY)
    publish(output, plan, "protocol.json")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "run", "qualify", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--authorize-cny", type=int)
    args, extra = parser.parse_known_args(argv)
    if args.action == "register":
        if extra:
            parser.error("unknown registration arguments")
        print(json.dumps({"id": register(args.output, authorized_CNY=args.authorize_cny)["id"]}))
        return 0
    return controller.main([args.action, "--output", str(args.output), *extra])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
