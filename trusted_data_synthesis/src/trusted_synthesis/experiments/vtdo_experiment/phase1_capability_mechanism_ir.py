from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_benchmark_capability_audit import (
    MechanismTier,
)
from trusted_synthesis.hashing import canonical_hash

CAPABILITY_MECHANISM_IR_VERSION = "finance_capability_mechanism_ir.v1"
CAPABILITY_MECHANISM_ACTION_GRAPH_VERSION = "finance_capability_mechanism_action_graph.v1"

VariantRole = Literal["resolved_control", "mechanism_required"]
MutationKind = Literal[
    "drop_required_dependency",
    "replace_required_tool",
    "remove_required_contract_tag",
    "premature_stop",
]

MECHANISM_IDS: tuple[str, ...] = (
    "finance.disambiguating_information_acquisition",
    "finance.typed_tool_plan_and_argument_recovery",
    "finance.dependent_compositional_calculation",
    "finance.bridge_semantic_alignment",
    "finance.candidate_verification_and_repair",
    "finance.cross_family_failure_recovery",
    "finance.state_dependent_control_and_stopping",
)

CORE_FAMILY_BY_MECHANISM: dict[str, str] = {
    "finance.disambiguating_information_acquisition": "finance.multi_hop_retrieval_join",
    "finance.typed_tool_plan_and_argument_recovery": "finance.branching_operation_plan",
    "finance.dependent_compositional_calculation": "finance.calculation_chain",
    "finance.bridge_semantic_alignment": "finance.definition_reconciliation",
    "finance.candidate_verification_and_repair": "finance.verification_sensitive_selection",
    "finance.cross_family_failure_recovery": "finance.recovery_guided_search",
    "finance.state_dependent_control_and_stopping": "finance.stopping_decision_control",
}

DEVELOPMENT_TIERS: tuple[MechanismTier, ...] = (
    "easy_control",
    "easy_control",
    "bridge",
    "bridge",
    "bridge",
    "bridge",
    "frontier",
    "frontier",
    "frontier",
    "frontier",
    "hard_control",
    "hard_control",
)

TIER_RANK: dict[MechanismTier, int] = {
    "easy_control": 1,
    "bridge": 2,
    "frontier": 3,
    "hard_control": 4,
}

REQUIRED_TAGS_BY_MECHANISM: dict[str, tuple[str, ...]] = {
    "finance.disambiguating_information_acquisition": (
        "competing_paths",
        "typed_disambiguation",
        "evidence_join",
    ),
    "finance.typed_tool_plan_and_argument_recovery": (
        "tool_choice",
        "observation_bound_arguments",
        "argument_repair",
    ),
    "finance.dependent_compositional_calculation": (
        "normalization_before_calculation",
        "three_dependent_operations",
        "intermediate_lineage",
    ),
    "finance.bridge_semantic_alignment": (
        "compatibility_rule",
        "qualified_resolution",
        "noncomparable_rejection",
    ),
    "finance.candidate_verification_and_repair": (
        "untrusted_candidate",
        "independent_replay",
        "localized_repair",
    ),
    "finance.cross_family_failure_recovery": (
        "typed_failure_observation",
        "failure_attribution",
        "field_specific_revision",
    ),
    "finance.state_dependent_control_and_stopping": (
        "public_completeness_invariant",
        "continue_or_stop_decision",
        "redundant_action_cost",
    ),
}

RECOVERY_ORIGIN_FAMILIES: tuple[str, ...] = (
    "information_acquisition",
    "tool_planning",
    "compositional_reasoning",
    "semantic_alignment",
    "verification",
    "control_stopping",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MechanismActionNode(FrozenModel):
    node_id: str = Field(min_length=1)
    action_kind: str = Field(min_length=1)
    depends_on: tuple[str, ...] = ()
    observation_dependencies: tuple[str, ...] = ()
    tool_id: str | None = None
    contract_tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_node(self) -> MechanismActionNode:
        if self.node_id in self.depends_on:
            raise ValueError("mechanism action cannot depend on itself")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("mechanism action duplicates a dependency")
        if len(set(self.contract_tags)) != len(self.contract_tags):
            raise ValueError("mechanism action duplicates a contract tag")
        return self


class MechanismActionGraph(FrozenModel):
    graph_id: str = Field(min_length=1)
    nodes: tuple[MechanismActionNode, ...] = Field(min_length=2)
    terminal_node_id: str = Field(min_length=1)
    required_edges: tuple[str, ...] = Field(min_length=1)
    graph_depth: int = Field(ge=2)
    schema_version: str = CAPABILITY_MECHANISM_ACTION_GRAPH_VERSION

    @model_validator(mode="after")
    def validate_graph(self) -> MechanismActionGraph:
        node_ids = tuple(item.node_id for item in self.nodes)
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("mechanism action graph duplicates a node")
        known: set[str] = set()
        edges: set[str] = set()
        for node in self.nodes:
            if not set(node.depends_on) <= known:
                raise ValueError("mechanism action graph is not topologically ordered")
            edges.update(edge_id(source, node.node_id) for source in node.depends_on)
            known.add(node.node_id)
        if self.terminal_node_id not in known:
            raise ValueError("mechanism action graph omits its terminal node")
        if not set(self.required_edges) <= edges:
            raise ValueError("mechanism action graph omits a required dependency")
        if self.graph_depth != graph_depth(self.nodes):
            raise ValueError("mechanism action graph depth is inconsistent")
        if self.graph_id != mechanism_action_graph_id(self):
            raise ValueError("mechanism action graph identity is invalid")
        return self


class MechanismMutationSpec(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation_kind: MutationKind
    target_node_id: str = Field(min_length=1)
    source_node_id: str | None = None
    target_contract_tag: str | None = None
    expected_violation_code: str = Field(min_length=1)


class MechanismMutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    observed_violation_codes: tuple[str, ...] = Field(min_length=1)
    expected_violation_code: str = Field(min_length=1)
    detected: bool

    @model_validator(mode="after")
    def validate_result(self) -> MechanismMutationResult:
        if self.detected != (self.expected_violation_code in self.observed_violation_codes):
            raise ValueError("mechanism mutation result is inconsistent")
        return self


class MechanismTaskVariant(FrozenModel):
    variant_id: str = Field(min_length=1)
    role: VariantRole
    mechanism_id: str = Field(min_length=1)
    mechanism_tier: MechanismTier
    artifact: CapabilitySensitiveTaskArtifact
    action_graph: MechanismActionGraph
    public_completeness_invariant: str = Field(min_length=1)
    compatibility_policy: tuple[str, ...] = Field(min_length=1)
    candidate_status: Literal["not_applicable", "valid", "invalid_localized"] = "not_applicable"
    recovery_origin_family: str | None = None
    contract_hash: str = Field(min_length=1)
    schema_version: str = CAPABILITY_MECHANISM_IR_VERSION

    @model_validator(mode="after")
    def validate_variant(self) -> MechanismTaskVariant:
        if self.mechanism_id not in MECHANISM_IDS:
            raise ValueError("mechanism task uses an unknown mechanism")
        if not self.artifact.verification.passed:
            raise ValueError("mechanism task lacks independent operation replay")
        metadata = self.artifact.task.public.metadata.get("v25_21_mechanism")
        if not isinstance(metadata, Mapping):
            raise ValueError("mechanism task omits its public mechanism contract")
        if (
            metadata.get("mechanism_id") != self.mechanism_id
            or metadata.get("mechanism_tier") != self.mechanism_tier
            or metadata.get("variant_role") != self.role
        ):
            raise ValueError("public mechanism contract differs from the typed variant")
        if self.role == "mechanism_required" and mechanism_contract_failures(self):
            raise ValueError("mechanism task contract fails closed")
        if self.mechanism_id == "finance.candidate_verification_and_repair":
            if self.role == "mechanism_required" and self.candidate_status == "not_applicable":
                raise ValueError("verification mechanism omits candidate status")
        elif self.candidate_status != "not_applicable":
            raise ValueError("non-verification mechanism declares candidate status")
        if self.mechanism_id == "finance.cross_family_failure_recovery":
            if self.role == "mechanism_required" and self.recovery_origin_family is None:
                raise ValueError("cross-family recovery omits origin family")
        elif self.recovery_origin_family is not None:
            raise ValueError("non-recovery mechanism declares recovery origin family")
        if self.contract_hash != mechanism_task_variant_hash(self):
            raise ValueError("mechanism task variant identity is invalid")
        return self


class MechanismDevelopmentGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    mechanism_tier: MechanismTier
    group_index: int = Field(ge=0)
    core_semantic_signature: str = Field(min_length=1)
    control: MechanismTaskVariant
    mechanism: MechanismTaskVariant
    mutations: tuple[MechanismMutationSpec, ...] = Field(min_length=4, max_length=4)
    group_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_group(self) -> MechanismDevelopmentGroup:
        if self.control.role != "resolved_control" or self.mechanism.role != "mechanism_required":
            raise ValueError("mechanism Development group has invalid variant roles")
        if {
            self.control.mechanism_id,
            self.mechanism.mechanism_id,
            self.mechanism_id,
        } != {self.mechanism_id}:
            raise ValueError("mechanism Development group mixes mechanisms")
        if (
            self.control.mechanism_tier != self.mechanism_tier
            or self.mechanism.mechanism_tier != self.mechanism_tier
        ):
            raise ValueError("mechanism Development group mixes tiers")
        control = self.control.artifact
        mechanism = self.mechanism.artifact
        if control.task.oracle.task_program != mechanism.task.oracle.task_program:
            raise ValueError("matched mechanism variants use different Programs")
        if control.projected_expected_output != mechanism.projected_expected_output:
            raise ValueError("matched mechanism variants use different Gold answers")
        if control.task.public.answer_schema != mechanism.task.public.answer_schema:
            raise ValueError("matched mechanism variants use different answer contracts")
        if tuple(item.evidence_version_id for item in control.evidence_bundle.evidence) != tuple(
            item.evidence_version_id for item in mechanism.evidence_bundle.evidence
        ):
            raise ValueError("matched mechanism variants use different Gold Evidence")
        if tuple(item.evidence_version_id for item in control.public_corpus.evidence) != tuple(
            item.evidence_version_id for item in mechanism.public_corpus.evidence
        ):
            raise ValueError("matched mechanism variants use different public Evidence scope")
        if control.artifact_id == mechanism.artifact_id:
            raise ValueError("matched mechanism variants collapse to one artifact")
        if self.group_id != mechanism_group_id(self):
            raise ValueError("mechanism Development group identity is invalid")
        if self.group_hash != mechanism_group_hash(self):
            raise ValueError("mechanism Development group hash is invalid")
        return self


def edge_id(source: str, target: str) -> str:
    return f"{source}->{target}"


def graph_depth(nodes: Sequence[MechanismActionNode]) -> int:
    depth: dict[str, int] = {}
    for node in nodes:
        depth[node.node_id] = 1 + max(
            (depth[item] for item in node.depends_on),
            default=0,
        )
    return max(depth.values())


def mechanism_action_graph_id(value: MechanismActionGraph) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"graph_id"}),
        prefix="finance_capability_mechanism_action_graph:",
    )


def mechanism_task_variant_hash(value: MechanismTaskVariant) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_hash", "variant_id"}),
        prefix="finance_capability_mechanism_variant:",
    )


def mechanism_group_id(value: MechanismDevelopmentGroup) -> str:
    return canonical_hash(
        {
            "mechanism_id": value.mechanism_id,
            "mechanism_tier": value.mechanism_tier,
            "group_index": value.group_index,
            "core_semantic_signature": value.core_semantic_signature,
        },
        prefix="finance_capability_mechanism_group_id:",
    )


def mechanism_group_hash(value: MechanismDevelopmentGroup) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"group_hash", "group_id"}),
        prefix="finance_capability_mechanism_group:",
    )


def _node(
    node_id: str,
    action_kind: str,
    depends_on: tuple[str, ...],
    tool_id: str | None,
    tags: tuple[str, ...] = (),
    observations: tuple[str, ...] = (),
) -> MechanismActionNode:
    return MechanismActionNode(
        node_id=node_id,
        action_kind=action_kind,
        depends_on=depends_on,
        tool_id=tool_id,
        contract_tags=tags,
        observation_dependencies=observations,
    )


def _tier_prefix(tier: MechanismTier) -> tuple[list[MechanismActionNode], str]:
    nodes = [_node("read_public_task", "read_public_task", (), None)]
    anchor = "read_public_task"
    labels = {
        "easy_control": (),
        "bridge": ("inspect_bridge_cue",),
        "frontier": ("inspect_bridge_cue", "inspect_frontier_ambiguity"),
        "hard_control": (
            "inspect_bridge_cue",
            "inspect_frontier_ambiguity",
            "inspect_hard_conflict",
        ),
    }[tier]
    for label in labels:
        nodes.append(
            _node(
                label,
                "inspect_public_constraint",
                (anchor,),
                "search_archive",
                observations=("previous public inspection result",),
            )
        )
        anchor = label
    return nodes, anchor


def _make_graph(
    nodes: Sequence[MechanismActionNode],
    required_edges: Sequence[str],
) -> MechanismActionGraph:
    values = {
        "nodes": tuple(nodes),
        "terminal_node_id": "stop",
        "required_edges": tuple(required_edges),
        "graph_depth": graph_depth(nodes),
    }
    provisional = MechanismActionGraph.model_construct(graph_id="pending", **values)
    return MechanismActionGraph(
        graph_id=mechanism_action_graph_id(provisional),
        **values,
    )


def make_control_action_graph(tier: MechanismTier) -> MechanismActionGraph:
    nodes, anchor = _tier_prefix(tier)
    nodes.extend(
        (
            _node(
                "execute_resolved_program",
                "execute_resolved_program",
                (anchor,),
                "calculator",
                ("resolved_control",),
            ),
            _node(
                "verify_resolved_output",
                "verify_output",
                ("execute_resolved_program",),
                "cross_check_evidence",
                observations=("calculator terminal output",),
            ),
            _node("stop", "stop", ("verify_resolved_output",), None),
        )
    )
    return _make_graph(
        nodes,
        (
            edge_id(anchor, "execute_resolved_program"),
            edge_id("execute_resolved_program", "verify_resolved_output"),
        ),
    )


def make_mechanism_action_graph(
    mechanism_id: str,
    tier: MechanismTier,
) -> MechanismActionGraph:
    nodes, anchor = _tier_prefix(tier)
    rows = _mechanism_rows(mechanism_id, tier, anchor)
    nodes.extend(rows[0])
    return _make_graph(nodes, rows[1])


def _mechanism_rows(
    mechanism_id: str,
    tier: MechanismTier,
    anchor: str,
) -> tuple[tuple[MechanismActionNode, ...], tuple[str, ...]]:
    nodes: tuple[MechanismActionNode, ...]
    edges: tuple[str, ...]
    if mechanism_id == MECHANISM_IDS[0]:
        nodes = (
            _node(
                "candidate_path_a",
                "search_candidate_path",
                (anchor,),
                "search_archive",
                ("competing_paths",),
            ),
            _node(
                "candidate_path_b",
                "search_candidate_path",
                (anchor,),
                "query_structured_fact",
                ("competing_paths",),
            ),
            _node(
                "typed_disambiguation",
                "disambiguate_candidates",
                ("candidate_path_a", "candidate_path_b"),
                "cross_check_evidence",
                ("typed_disambiguation",),
                ("both candidate path observations",),
            ),
            _node(
                "evidence_join",
                "join_required_records",
                ("typed_disambiguation",),
                "query_structured_fact",
                ("evidence_join",),
                ("typed compatible candidate set",),
            ),
            _node("execute_program", "execute_program", ("evidence_join",), "calculator"),
            _node("verify_output", "verify_output", ("execute_program",), "cross_check_evidence"),
            _node("stop", "stop", ("verify_output",), None),
        )
        edges = (
            edge_id("candidate_path_a", "typed_disambiguation"),
            edge_id("candidate_path_b", "typed_disambiguation"),
            edge_id("typed_disambiguation", "evidence_join"),
        )
    elif mechanism_id == MECHANISM_IDS[1]:
        nodes = (
            _node(
                "choose_typed_tool",
                "choose_typed_tool",
                (anchor,),
                "search_archive",
                ("tool_choice",),
            ),
            _node(
                "construct_arguments",
                "construct_typed_arguments",
                ("choose_typed_tool",),
                "query_structured_fact",
                ("observation_bound_arguments",),
                ("selected tool schema",),
            ),
            _node(
                "tool_failure_observation",
                "observe_typed_argument_failure",
                ("construct_arguments",),
                "query_structured_fact",
                observations=("Host typed validation response",),
            ),
            _node(
                "argument_patch",
                "patch_failed_argument",
                ("tool_failure_observation",),
                "query_structured_fact",
                ("argument_repair",),
                ("typed failure field",),
            ),
            _node(
                "tool_retry",
                "retry_with_repaired_arguments",
                ("argument_patch",),
                "query_structured_fact",
                observations=("argument patch",),
            ),
            _node("execute_program", "execute_program", ("tool_retry",), "calculator"),
            _node("stop", "stop", ("execute_program",), None),
        )
        edges = (
            edge_id("tool_failure_observation", "argument_patch"),
            edge_id("argument_patch", "tool_retry"),
        )
    elif mechanism_id == MECHANISM_IDS[2]:
        nodes = (
            _node(
                "normalize_inputs",
                "normalize_unit_period_definition",
                (anchor,),
                "normalize_metric_unit_period",
                ("normalization_before_calculation",),
            ),
            _node(
                "derived_step_1",
                "derived_operation",
                ("normalize_inputs",),
                "calculator",
                ("three_dependent_operations", "intermediate_lineage"),
                ("normalized inputs",),
            ),
            _node(
                "derived_step_2",
                "derived_operation",
                ("derived_step_1",),
                "calculator",
                ("three_dependent_operations", "intermediate_lineage"),
                ("derived step 1 output",),
            ),
            _node(
                "derived_step_3",
                "derived_operation",
                ("derived_step_2",),
                "calculator",
                ("three_dependent_operations", "intermediate_lineage"),
                ("derived step 2 output",),
            ),
            _node(
                "verify_output",
                "verify_intermediate_and_final_outputs",
                ("derived_step_3",),
                "cross_check_evidence",
            ),
            _node("stop", "stop", ("verify_output",), None),
        )
        edges = (
            edge_id("normalize_inputs", "derived_step_1"),
            edge_id("derived_step_1", "derived_step_2"),
            edge_id("derived_step_2", "derived_step_3"),
        )
    elif mechanism_id == MECHANISM_IDS[3]:
        normalizer = (
            "query_structured_fact" if tier == "easy_control" else "normalize_metric_unit_period"
        )
        nodes = (
            _node(
                "inspect_semantic_context",
                "inspect_semantic_context",
                (anchor,),
                "query_structured_fact",
            ),
            _node(
                "apply_compatibility_rule",
                "apply_public_compatibility_rule",
                ("inspect_semantic_context",),
                normalizer,
                ("compatibility_rule",),
                ("unit period alias and definition fields",),
            ),
            _node(
                "resolve_or_reject",
                "resolve_with_qualifier_or_reject",
                ("apply_compatibility_rule",),
                "cross_check_evidence",
                ("qualified_resolution", "noncomparable_rejection"),
                ("compatibility decision",),
            ),
            _node("execute_program", "execute_program", ("resolve_or_reject",), "calculator"),
            _node("stop", "stop", ("execute_program",), None),
        )
        edges = (
            edge_id("inspect_semantic_context", "apply_compatibility_rule"),
            edge_id("apply_compatibility_rule", "resolve_or_reject"),
        )
    elif mechanism_id == MECHANISM_IDS[4]:
        nodes = (
            _node(
                "untrusted_candidate",
                "receive_untrusted_candidate",
                (anchor,),
                None,
                ("untrusted_candidate",),
            ),
            _node(
                "independent_replay",
                "independently_replay_candidate",
                ("untrusted_candidate",),
                "calculator",
                ("independent_replay",),
                ("untrusted candidate fields",),
            ),
            _node(
                "repair_or_confirm",
                "localized_repair_or_confirmation",
                ("independent_replay",),
                "cross_check_evidence",
                ("localized_repair",),
                ("independent replay difference",),
            ),
            _node(
                "regression_check",
                "preserve_unaffected_fields",
                ("repair_or_confirm",),
                "cross_check_evidence",
            ),
            _node("stop", "stop", ("regression_check",), None),
        )
        edges = (
            edge_id("untrusted_candidate", "independent_replay"),
            edge_id("independent_replay", "repair_or_confirm"),
        )
    elif mechanism_id == MECHANISM_IDS[5]:
        nodes = (
            _node(
                "initial_action",
                "execute_initial_family_action",
                (anchor,),
                "query_structured_fact",
            ),
            _node(
                "typed_failure_observation",
                "observe_typed_failure",
                ("initial_action",),
                "query_structured_fact",
                ("typed_failure_observation",),
                ("Host typed failure without answer",),
            ),
            _node(
                "failure_attribution",
                "attribute_failure_to_field_or_action",
                ("typed_failure_observation",),
                "cross_check_evidence",
                ("failure_attribution",),
                ("typed error code and failed selector",),
            ),
            _node(
                "revised_action",
                "revise_only_failed_field_or_action",
                ("failure_attribution",),
                "query_structured_fact",
                ("field_specific_revision",),
                ("localized failure attribution",),
            ),
            _node(
                "post_repair_verification",
                "verify_post_repair_completion",
                ("revised_action",),
                "cross_check_evidence",
            ),
            _node("stop", "stop", ("post_repair_verification",), None),
        )
        edges = (
            edge_id("typed_failure_observation", "failure_attribution"),
            edge_id("failure_attribution", "revised_action"),
        )
    elif mechanism_id == MECHANISM_IDS[6]:
        nodes = (
            _node(
                "gather_partial_state", "gather_partial_state", (anchor,), "query_structured_fact"
            ),
            _node(
                "completeness_check",
                "evaluate_public_completeness_invariant",
                ("gather_partial_state",),
                "cross_check_evidence",
                ("public_completeness_invariant",),
                ("currently resolved public roles",),
            ),
            _node(
                "continue_or_stop",
                "choose_continue_or_stop",
                ("completeness_check",),
                None,
                ("continue_or_stop_decision",),
                ("completeness invariant result",),
            ),
            _node(
                "resolve_missing_role",
                "resolve_missing_required_role",
                ("continue_or_stop",),
                "query_structured_fact",
            ),
            _node(
                "final_completeness_check",
                "recheck_public_completeness_invariant",
                ("resolve_missing_role",),
                "cross_check_evidence",
                ("redundant_action_cost",),
            ),
            _node("stop", "stop", ("final_completeness_check",), None),
        )
        edges = (
            edge_id("completeness_check", "continue_or_stop"),
            edge_id("continue_or_stop", "resolve_missing_role"),
            edge_id("final_completeness_check", "stop"),
        )
    else:
        raise ValueError(f"unknown capability mechanism: {mechanism_id}")
    return nodes, edges


def mechanism_contract_failures(value: MechanismTaskVariant) -> tuple[str, ...]:
    return mechanism_contract_failures_raw(
        mechanism_id=value.mechanism_id,
        tier=value.mechanism_tier,
        graph=value.action_graph.model_dump(mode="json"),
        allowed_tools=set(value.artifact.task.public.allowed_tools),
        compatibility_policy=value.compatibility_policy,
        candidate_status=value.candidate_status,
        recovery_origin_family=value.recovery_origin_family,
    )


def mechanism_contract_failures_raw(
    *,
    mechanism_id: str,
    tier: MechanismTier,
    graph: Mapping[str, Any],
    allowed_tools: set[str],
    compatibility_policy: Sequence[str],
    candidate_status: str,
    recovery_origin_family: str | None,
) -> tuple[str, ...]:
    failures: set[str] = set()
    raw_nodes = graph.get("nodes")
    if not isinstance(raw_nodes, list):
        return ("action_graph_malformed",)
    nodes = {
        str(item.get("node_id")): item
        for item in raw_nodes
        if isinstance(item, Mapping) and item.get("node_id")
    }
    if len(nodes) != len(raw_nodes):
        failures.add("action_graph_malformed")
    edges = {
        edge_id(str(source), node_id)
        for node_id, item in nodes.items()
        for source in item.get("depends_on", ())
    }
    if not {str(item) for item in graph.get("required_edges", ())} <= edges:
        failures.add("required_dependency_missing")
    tags = {str(tag) for item in nodes.values() for tag in item.get("contract_tags", ())}
    if not set(REQUIRED_TAGS_BY_MECHANISM[mechanism_id]) <= tags:
        failures.add("required_contract_tag_missing")
    if any(
        item.get("tool_id") is not None and item.get("tool_id") not in allowed_tools
        for item in nodes.values()
    ):
        failures.add("unregistered_tool")
    terminal = nodes.get(str(graph.get("terminal_node_id")))
    if terminal is None or terminal.get("action_kind") != "stop":
        failures.add("terminal_contract_broken")
    if mechanism_id == MECHANISM_IDS[2]:
        if sum(item.get("action_kind") == "derived_operation" for item in nodes.values()) < 3:
            failures.add("dependent_operation_depth_insufficient")
    if mechanism_id == MECHANISM_IDS[3]:
        minimum_rules = 1 if tier == "easy_control" else 2
        if len(compatibility_policy) < minimum_rules:
            failures.add("semantic_bridge_policy_incomplete")
    if mechanism_id == MECHANISM_IDS[4]:
        if candidate_status not in {"valid", "invalid_localized"}:
            failures.add("untrusted_candidate_contract_missing")
    if mechanism_id == MECHANISM_IDS[5]:
        if recovery_origin_family not in RECOVERY_ORIGIN_FAMILIES:
            failures.add("recovery_origin_family_missing")
    return tuple(sorted(failures))


def make_mutation_specs(graph: MechanismActionGraph) -> tuple[MechanismMutationSpec, ...]:
    source, target = graph.required_edges[0].split("->", maxsplit=1)
    tag_counts = {
        tag: sum(tag in item.contract_tags for item in graph.nodes)
        for tag in {value for item in graph.nodes for value in item.contract_tags}
    }
    tagged = next(
        item for item in graph.nodes if any(tag_counts[tag] == 1 for tag in item.contract_tags)
    )
    target_tag = next(tag for tag in tagged.contract_tags if tag_counts[tag] == 1)
    tool_node = next(item for item in graph.nodes if item.tool_id is not None)
    early = next(item for item in graph.nodes if item.node_id != graph.terminal_node_id)
    values = (
        ("drop_required_dependency", target, source, None, "required_dependency_missing"),
        ("replace_required_tool", tool_node.node_id, None, None, "unregistered_tool"),
        (
            "remove_required_contract_tag",
            tagged.node_id,
            None,
            target_tag,
            "required_contract_tag_missing",
        ),
        ("premature_stop", early.node_id, None, None, "terminal_contract_broken"),
    )
    output = []
    for kind, target_node, source_node, tag, violation in values:
        payload = {
            "mutation_kind": kind,
            "target_node_id": target_node,
            "source_node_id": source_node,
            "target_contract_tag": tag,
            "expected_violation_code": violation,
        }
        output.append(
            MechanismMutationSpec(
                mutation_id=canonical_hash(
                    {"graph_id": graph.graph_id, **payload},
                    prefix="finance_capability_mechanism_mutation:",
                ),
                **payload,
            )
        )
    return tuple(output)


def evaluate_mutation(
    variant: MechanismTaskVariant,
    mutation: MechanismMutationSpec,
) -> MechanismMutationResult:
    graph = json.loads(json.dumps(variant.action_graph.model_dump(mode="json")))
    nodes = graph["nodes"]
    if mutation.mutation_kind == "drop_required_dependency":
        node = next(item for item in nodes if item["node_id"] == mutation.target_node_id)
        node["depends_on"] = [
            item for item in node["depends_on"] if item != mutation.source_node_id
        ]
    elif mutation.mutation_kind == "replace_required_tool":
        node = next(item for item in nodes if item["node_id"] == mutation.target_node_id)
        node["tool_id"] = "unregistered_mutation_tool"
    elif mutation.mutation_kind == "remove_required_contract_tag":
        node = next(item for item in nodes if item["node_id"] == mutation.target_node_id)
        node["contract_tags"] = [
            item for item in node["contract_tags"] if item != mutation.target_contract_tag
        ]
    elif mutation.mutation_kind == "premature_stop":
        graph["terminal_node_id"] = mutation.target_node_id
    else:
        raise AssertionError(f"unsupported mutation: {mutation.mutation_kind}")
    failures = mechanism_contract_failures_raw(
        mechanism_id=variant.mechanism_id,
        tier=variant.mechanism_tier,
        graph=graph,
        allowed_tools=set(variant.artifact.task.public.allowed_tools),
        compatibility_policy=variant.compatibility_policy,
        candidate_status=variant.candidate_status,
        recovery_origin_family=variant.recovery_origin_family,
    )
    return MechanismMutationResult(
        mutation_id=mutation.mutation_id,
        observed_violation_codes=failures,
        expected_violation_code=mutation.expected_violation_code,
        detected=mutation.expected_violation_code in failures,
    )
