"""Prospective rules and fixed twelve-session population, not an answer menu."""

import subprocess

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import SPECS, node
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient.rules import (
    rule as previous_rule,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.stage import SYSTEM
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import TransportConfig
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    record as config_record,
)

BASELINE = "ef7fb9a11b2c9b511afabf90cf010f20676b1d86"
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_finqa_support_exploration/j1_j2_nd_3rep_20260908"
)
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/exper"
    "iments/finance_qa_vnext_finqa_support_exploration"
)
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_finqa_support_exploration.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_finqa_support_exploration.py"
PARENT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_binding_view/e1_j2_e_v0v1_2rep_20260908"
QUOTIENT_PARENT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_quotient/j2_existing_20260908"
VERSION = "finqa_prospective_numeric_public_behavior.v2"
D_GUIDANCE = (
    "You may consider organizing the calculation throug"
    "h evidence-supported changes in components, "
    "while still choosing a valid method yourself. Execute only steps relevant to the goal; "
    "do not repeat calculations merely to create diversity."
)
# Balanced fixed dispatch ordering, not adaptive to completion or inferred diversity.
LABELS = tuple(
    f"{task}_{stratum}_{rep:02d}"
    for rep in range(1, 4)
    for task, stratum in (("J1", "N"), ("J2", "D"), ("J1", "D"), ("J2", "N"))
)


class Config(TransportConfig):
    def as_record(self):
        base = super().as_record()
        if self.system_prompt != SYSTEM:
            require(self.system_prompt == SYSTEM + "\n\n" + D_GUIDANCE, "config.exact_D")
            base["messages_policy"] = (
                "fixed generic decomposition exploration system plu"
                "s canonical current public request; stateless"
            )
        return config_record(
            "transport_config",
            **{k: v for k, v in base.items() if k not in {"id", "schema_version"}},
        )


def configuration(stratum):
    require(stratum in {"N", "D"}, "config.stratum")
    return Config(system_prompt=SYSTEM + ("\n\n" + D_GUIDANCE if stratum == "D" else ""))


def registrations():
    rows = []
    for ordinal, label in enumerate(LABELS, 1):
        task, stratum, replicate = label.split("_")
        rows.append(
            record(
                "support_exploration_registration",
                label=label,
                ordinal=ordinal,
                task_key=task,
                task_id=SPECS[task][1],
                exploration_stratum=stratum,
                replicate=int(replicate),
                condition="E",
                view_condition="V1",
                expression_condition="P",
                feedback_condition="R",
                fresh_session=True,
                maximum_actions=12,
                maximum_submissions=32,
                maximum_provider_attempts=32,
                model_configuration_id=configuration(stratum).as_record()["id"],
            )
        )
    return rows


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        ":(exclude)" + PACKAGE,
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_finqa_support_exploration",
        ":(exclude)" + DOCUMENT,
        ":(exclude)" + TEST,
    ]
    require(
        not subprocess.check_output(
            ["git", "diff", "--name-only", BASELINE, "--", *paths], cwd=root
        ),
        "support.history_changes",
    )
    require(
        not subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=root),
        "support.history_uncommitted",
    )
    return {"baseline": BASELINE, "old_tracked_files_unchanged": True, "old_controls_rerun": False}


def rules():
    return record(
        "support_exploration_rules",
        version=VERSION,
        historical_rule_reference=previous_rule()["id"],
        historical_assignments_reused=False,
        retrospective_rule_redefinition=False,
        tasks=["J1", "J2"],
        source_mixture={"N": "1/2", "D": "1/2"},
        new_task_weights={"J1": "1/2", "J2": "1/2"},
        labels=list(LABELS),
        interpretation_frozen_before_new_responses=True,
        operator_domain=["read", "add", "subtract", "multiply", "divide"],
        additional_operators="remain legal in Runtime; uncovered full graph mapp"
        "ing is UNDETERMINED, never failed validity",
        commutation=["add", "multiply"],
        constant_edges="exact public constant IDs, not source values",
        retained="all actual operation/Update occurrences, rejected "
        "proposals and Final; actual source and Claim edges"
        ", "
        "adjustment boundaries, duplicate predecessors; no "
        "deletion to manufacture equal/unequal classes",
        unsupported_lifecycle="interleaved Action/Update not covered => full proj"
        "ection UNDETERMINED; raw package kept",
        public_judgment_rubric={
            "population": "every valid-JSON kind=action proposal in each comp"
            "lete valid trajectory, including schema/semantic r"
            "ejections",
            "labels": ["REVIEWED", "UNDETERMINED"],
            "evidence": "full original reason/subgoal and raw hash; manual "
            "finite key object/period/value/sign/method commitm"
            "ents",
            "underspecification": "record explicitly; never fill a chosen current obj"
            "ect from actual input or target",
            "equivalence": "paraphrases of the same explicit proposition may s"
            "hare a label; do not hash prose or stratum into a "
            "behavior class",
            "knowledge_edges": "only explicitly asserted prior accepted results, t"
            "ied to their actual producer IDs",
            "uncertainty": "unexplained or contradictory interpretation stays "
            "UNDETERMINED; no post-result rubric changes",
            "review_limits": "post-sampling unblinded human interpretation; quot"
            "e checker is not semantic certification",
        },
        support_graph="separate actual Final-ancestor graph; ignore judgm"
        "ents/adjustment/unused nodes only for this diagnos"
        "tic",
        nonredundant_witness="predefined source-symbolic intermediate pairs must"
        " both be executed, accepted and consumed into Fina"
        "l; "
        "also require the actual direct combine operation o"
        "n those Claim occurrences. Merely proposing a plan"
        ", adding unused "
        "work or using a different prompt is not a witness."
        " Unclassified support differences remain descripti"
        "ve/undetermined",
        named_probe_scope="annual totals versus component changes; not exhaus"
        "tive categories, not instructions to model, not Co"
        "ntribution",
        finite_law="within task across the prospectively equal-weight "
        "N/D exploration source, count valid trajectories p"
        "er class; "
        "keep N/D component success counts and original pro"
        "mpts; any unknown valid mapping makes full pi null",
        mixture_success_law="q_x=(m_N+m_D)/6; pi_x(z|Y=1)=(n_Nz+n_Dz)/(m_N+m_D)"
        ", not half of each conditional law",
        class_internal_origin="save actual N/D/trajectory composition; null train"
        "ing weights, no row/token-uniform sampler",
        collection="12 fresh sessions once, each 12 ops/32 submissions"
        "/32 attempts; total attempts<=384; no replacement,"
        " extension or success-seeking resampling",
        materialization="all admitted exact original responses from complet"
        "e valid sessions, real HTTP inputs including N/D; "
        "entire trajectory package",
        stopping="close after fixed collection and measurements even"
        " without new mechanisms; no Student, GPU, training"
        " or VTDO",
        full_behavior_rule="exact occurrence-labeled DAG isomorphism; IDs bije"
        "ctive, no graph-hash-only proof",
        named_publication_cut=(
            "J2 combine Claim must be Final's actual answer Claim. "
            "J1 combine must directly feed the numerator of divide by "
            "an actual net_base add Claim, then multiply by constant:100 "
            "as the actual Final answer; other shapes remain unclassified, not invalid."
        ),
        maximum_reserved_tokens=41287680,
        novelty=None,
        contribution=None,
        student_utility=None,
    )


def probes(task):
    f = task["selected"]
    a = node
    if task["key"] == "J2":
        q1, p1, q0, p0 = f
        dq, dp = a("subtract", q1, q0), a("subtract", p1, p0)
        return {
            "annual_new": a("multiply", q1, p1),
            "annual_base": a("multiply", q0, p0),
            "quantity_change": dq,
            "price_change": dp,
            "quantity_effect_base_price": a("multiply", dq, p0),
            "price_effect_new_quantity": a("multiply", q1, dp),
            "quantity_effect_new_price": a("multiply", dq, p1),
            "price_effect_base_quantity": a("multiply", q0, dp),
            "complete_target": task["target"],
        }
    require(task["key"] == "J1", "probes.new_tasks")
    c1, t1, c0, t0 = f
    return {
        "net_new": a("add", c1, t1),
        "net_base": a("add", c0, t0),
        "cost_change": a("subtract", c1, c0),
        "signed_tax_change": a("subtract", t1, t0),
        "net_change": a("add", a("subtract", c1, c0), a("subtract", t1, t0)),
        "complete_target": task["target"],
    }
