"""New given-sources runtime; old snapshot and training modules are immutable.

The model uses training-compatible read_source(source_id, unit). A frozen public
map resolves that source ID to the original raw object/pointer. Numeric values,
unit conversions and actual periods remain source bound, so the unchanged
financial support assessor can consume the tool result. No answer is consulted.
"""

import copy
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_budget_reevaluation_adapter_20260915 as isolation

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import worker as training
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import assessment, runtime
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

VERSION = "given_public_source_view_runtime.v1:20260915"
SELECTION_SYSTEM = runtime.SYSTEM[runtime.SYSTEM.index("select_max arguments:") :]
SYSTEM = training.SYSTEM + "\n" + training.GUIDANCE["neutral"] + "\n" + SELECTION_SYSTEM
PUBLIC_FIELDS = {
    "question",
    "sources",
    "period_contract",
    "quantity_contract",
    "source_policy",
    "tool_contract",
}
TOOLS = {"read_source", "calculate", "select_max", "compare", "lookup_selected"}


def binding():
    return p.record(
        "source_view_runtime_binding",
        version=VERSION,
        source_sha256=p.sha(Path(__file__)),
        SYSTEM_sha256=p.sha(SYSTEM),
        original_runtime_sha256=p.sha(Path(runtime.__file__)),
        original_assessment_sha256=p.sha(Path(assessment.__file__)),
        training_tools_sha256=p.sha(Path(training.__file__)),
        read_arguments=["source_id", "unit"],
        mechanical_pointer_map_only=True,
        financial_qualification_unchanged=True,
        online_and_replay_same_runtime=True,
        old_snapshot_results_not_replaced=True,
    )


class SourceViewSources:
    def __init__(self, public):
        self.public = copy.deepcopy(public)
        self.references = {row["source_id"]: row for row in self.public["sources"]}
        p.require(
            len(self.references) == len(self.public["sources"]), "source_view.unique_source_ids"
        )

    def descriptors(self):
        return copy.deepcopy(self.public["sources"])

    def read_source(self, arguments):
        # The real training primitive checks the declared record, parses its
        # original amount, and executes compatible unit conversion.
        result = training.read_source(arguments, self.public)
        source = self.references[arguments["source_id"]]
        return {
            **result,
            "source_id": source["raw_object_id"],
            "native_pointer": source["native_pointer"],
            "concept": source["concept"],
            "record": copy.deepcopy(source["record"]),
            "actual_period": runtime.actual_period(source["record"]),
            "source_view_id": source["source_id"],
            "source_mapping_is_mechanical_not_a_private_fact_lookup": True,
        }


def public_document(messages, identity, sources):
    p.require(
        set(identity) == runtime.IDENTITY_FIELDS and identity["family"] in runtime.FAMILIES,
        "source_view.public_identity",
    )
    p.require(
        len(messages) == 1
        and set(messages[0]) == {"role", "content"}
        and messages[0]["role"] == "user",
        "source_view.one_initial_user_message",
    )
    p.require(
        p.sha(p.encode(messages)) == identity["public_messages_sha256"],
        "source_view.new_public_hash",
    )
    public = training.strict_json(messages[0]["content"])
    p.require(
        set(public) == PUBLIC_FIELDS and public == sources.public,
        "source_view.exact_public_material",
    )
    p.require(
        public["period_contract"]["task_id"] == identity["task_id"],
        "source_view.original_task_period_contract",
    )
    return public


def execute(tool, arguments, sources, outputs):
    p.require(tool in TOOLS, "source_view.unknown_tool")
    return runtime.execute(tool, arguments, sources, outputs)


def build_runtime():
    registered = binding()

    def record(kind, **fields):
        if kind == "evaluation_session":
            fields.update(
                source_view_runtime_binding_id=registered["id"],
                utility_environment="J_sources_not_J_snapshot",
                starts_without_Probe_history=True,
            )
        return runtime.record(kind, **fields)

    namespace = {
        **vars(runtime),
        "SYSTEM": SYSTEM,
        "public_document": public_document,
        "execute": execute,
        "record": record,
    }
    generate = isolation.clone_function(runtime.generate, namespace)
    offline = {**vars(assessment), "generate": generate}
    replay = isolation.clone_function(assessment.replay_session, offline)
    offline["replay_session"] = replay
    assess = isolation.clone_function(assessment.assess_session, offline)
    return SimpleNamespace(
        generate=generate,
        replay_session=replay,
        assess_session=assess,
        Sources=SourceViewSources,
        SYSTEM=SYSTEM,
        binding=registered,
    )
