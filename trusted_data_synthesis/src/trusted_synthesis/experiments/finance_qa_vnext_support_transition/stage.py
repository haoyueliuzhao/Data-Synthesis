"""Freeze a new measurement layer over the immutable completed exploration source."""

from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore

from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require, sha
from ..finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_directory,
    verify_source_snapshot,
)
from .comparison import compare_all, comparison_contract
from .distribution import build_distribution
from .guards import guard_report, measurement_guard
from .projection import project_entry
from .rules import STAGE, measurement_rule
from .source import history_inventory, load_inputs, preserved_sources

ARTIFACT_PREFIX = "trusted_data_synthesis/artifacts/qa_vnext_support_transition"
RUN_TAG = "support_transition_grounding_v1_20260907"
DESIGN_PATH = Path(
    "/home/zhuxinrui/.codex/attachments/cca8db4a-3dea-4980-a1a4-3abfaca8564a/pasted-text.txt"
)
DESIGN_BYTES = 25_030
DESIGN_SHA256 = "f983897faf58560a818cfa6ac6d41f8c450d149a1c661851924759f1ae36c030"


def _target(root, output):
    root, output = root.resolve(), output.resolve()
    require(
        output.is_relative_to(root / ARTIFACT_PREFIX) and output != root / ARTIFACT_PREFIX,
        "support_transition.additive_output_directory",
    )
    return root, output


def freeze_condition(inputs, rule, implementation):
    bindings = inputs["source_binding_checks"]
    generation = inputs["generation_condition"]
    return record(
        "support_transition_condition",
        stage=STAGE,
        run_tag=RUN_TAG,
        generation_condition_id=generation["id"],
        original_generation_rule_id=generation["rule_id"],
        rule_id=rule["id"],
        implementation_id=implementation["id"],
        old_comparison_contract_id=inputs["old_comparison_contract"]["id"],
        old_quotient_id=inputs["old_quotient"]["id"],
        old_report_id=inputs["old_report"]["id"],
        source_anchor_id=inputs["source_anchor"]["id"],
        source_binding_checks_id=bindings["id"],
        registration_ids=bindings["registration_ids"],
        qualification_ids=bindings["qualification_ids"],
        session_ids=bindings["session_ids"],
        qualified_qualification_ids=bindings["qualified_qualification_ids"],
        frozen_outcomes=bindings["frozen_outcomes"],
        registered_session_count=8,
        qualified_session_count=3,
        known_failure_count=5,
        qualified_labels=bindings["qualified_labels"],
        original_profile_ids=bindings["profile_ids"],
        original_configuration_ids=bindings["model_configuration_ids"],
        new_interpretation_positions=bindings["newly_interpreted_sequences"],
        target_new_event_count=7,
        existing_resolved_event_count=14,
        original_qualified_event_count=42,
        original_qualified_admitted_count=21,
        original_qualified_unadmitted_count=21,
        original_all_event_count=202,
        registered_pairs=[["N03", "E04"], ["N03", "E02"], ["E02", "E04"]],
        historical_success_fractions={
            "N": {"numerator": 1, "denominator": 4},
            "E": {"numerator": 2, "denominator": 4},
            "exploration": {"numerator": 3, "denominator": 8},
        },
        original_generation_condition_rehashed_or_modified=False,
        design_sha256=DESIGN_SHA256,
        design_bytes=DESIGN_BYTES,
        inference_scope="post-observation finite measurement rule instance, not blinded",
        unsupported_events_may_remain_undetermined=True,
        target_class_count=None,
        maximum_new_provider_calls=0,
        maximum_runtime_executions=0,
        qualification_replay=False,
        tokenization=False,
        student_or_gpu=False,
        source_profile_composition_preserved_for_future_materialization=True,
        old_mainline="remains_paused",
        final_training_weights=None,
    )


def prepare(root: Path, output: Path):
    root, output = _target(root, output)
    directory = output / "preparation"
    with measurement_guard() as counts:
        if directory.exists():
            verify_directory(directory, kind="support_transition_preparation_manifest")
            verify_source_snapshot(
                root, read_json((directory / "implementation.json").read_bytes())
            )
            return read_json((directory / "condition.json").read_bytes())
        inputs = load_inputs(root)
        implementation = source_snapshot(root)
        rule = measurement_rule()
        condition = freeze_condition(inputs, rule, implementation)
        contract = comparison_contract(condition, inputs["generation_condition"], rule)
        design = DESIGN_PATH.read_bytes()
        require(
            len(design) == DESIGN_BYTES and sha(design) == DESIGN_SHA256,
            "support_transition.design_bytes",
        )
        store = DurableStore(directory)
        store.write("experiment_design.txt", design)
        for name, value in (
            ("implementation", implementation),
            ("condition", condition),
            ("rule", rule),
            ("comparison_contract", contract),
            ("generation_condition_reference", inputs["generation_condition"]),
            ("source_anchor", inputs["source_anchor"]),
            ("source_binding_checks", inputs["source_binding_checks"]),
            ("representation_references", inputs["representation_references"]),
            ("history_inventory", history_inventory(root)),
            ("source_preservation", preserved_sources(root)),
            ("execution_guards", guard_report(counts, "preparation")),
        ):
            store.json(name + ".json", value)
        seal_directory(
            store,
            kind="support_transition_preparation_manifest",
            condition_id=condition["id"],
            rule_id=rule["id"],
        )
        return condition


def run(root: Path, output: Path):
    root, output = _target(root, output)
    directory = output / "preparation"
    measurement = output / "measurement"
    with measurement_guard() as counts:
        manifest = verify_directory(directory, kind="support_transition_preparation_manifest")
        frozen = {
            name: read_json((directory / (name + ".json")).read_bytes())
            for name in (
                "implementation",
                "condition",
                "rule",
                "comparison_contract",
                "generation_condition_reference",
                "source_anchor",
                "source_binding_checks",
                "representation_references",
                "history_inventory",
                "source_preservation",
            )
        }
        condition, rule = frozen["condition"], frozen["rule"]
        identity(condition, "support_transition_condition")
        require(rule == measurement_rule(), "support_transition.frozen_rule_changed")
        verify_source_snapshot(root, frozen["implementation"])
        if measurement.exists():
            sealed = verify_directory(measurement, kind="support_transition_measurement_manifest")
            require(
                sealed["condition_id"] == condition["id"], "support_transition.readback_condition"
            )
            return read_json((measurement / "report.json").read_bytes())
        inputs = load_inputs(root)
        require(
            inputs["source_anchor"] == frozen["source_anchor"]
            and inputs["source_binding_checks"] == frozen["source_binding_checks"]
            and inputs["generation_condition"] == frozen["generation_condition_reference"]
            and inputs["representation_references"] == frozen["representation_references"],
            "support_transition.frozen_inputs_changed",
        )
        require(
            freeze_condition(inputs, rule, frozen["implementation"]) == condition,
            "support_transition.measurement_condition_changed",
        )
        generation = inputs["generation_condition"]
        contract = comparison_contract(condition, generation, rule)
        require(
            contract == frozen["comparison_contract"],
            "support_transition.comparison_contract_changed",
        )
        projections = [
            project_entry(e, condition, generation, rule, contract) for e in inputs["entries"]
        ]
        pairs = compare_all(inputs["entries"], projections, condition, generation, rule, contract)
        distribution = build_distribution(
            inputs["entries"], projections, pairs, condition, generation, rule, contract
        )
        from .controls import run_controls

        controls = run_controls(inputs, projections, pairs, condition, rule, contract)
        require(controls["all_expected_outcomes"], "support_transition.direct_controls_failed")
        after = history_inventory(root)
        require(
            after == frozen["history_inventory"]
            and preserved_sources(root) == frozen["source_preservation"],
            "support_transition.historical_bytes_changed",
        )
        guards = guard_report(counts, "measurement_and_direct_controls")
        report = record(
            "support_transition_report",
            stage=STAGE,
            measurement_condition_id=condition["id"],
            generation_condition_id=generation["id"],
            original_generation_rule_id=generation["rule_id"],
            rule_id=rule["id"],
            comparison_contract_id=contract["id"],
            source_commit=frozen["implementation"]["source_commit"],
            implementation_id=frozen["implementation"]["id"],
            preparation_manifest_id=manifest["id"],
            original_report_id=inputs["old_report"]["id"],
            original_quotient_id=inputs["old_quotient"]["id"],
            source_anchor_id=inputs["source_anchor"]["id"],
            registered_sessions=8,
            original_qualified_sessions=3,
            original_known_failures=5,
            original_all_submissions=202,
            original_qualified_submissions=42,
            original_qualified_admitted_submissions=21,
            original_qualified_unadmitted_submissions=21,
            mapped_qualified_sessions=sum(p["supported"] for p in projections),
            assignment_count=len(distribution["assignments"]),
            formal_class_count=distribution["complete_class_count"],
            new_W_support=distribution["W_support"],
            complete_quotient_measurement_closed=distribution[
                "complete_quotient_measurement_closed"
            ],
            newly_interpreted_events=sum(p["newly_interpreted_event_count"] for p in projections),
            reused_old_interpretations=sum(p["reused_interpretation_count"] for p in projections),
            unresolved_labels=[p["label"] for p in projections if p["status"] == "undetermined"],
            projection_ids=[p["id"] for p in projections],
            pair_ids=[p["id"] for p in pairs],
            registered_pair_count=3,
            distribution=distribution,
            controls_id=controls["id"],
            all_direct_controls_expected=controls["all_expected_outcomes"],
            execution_guards=guards,
            history_inventory_id=after["id"],
            all_historical_bytes_unchanged=True,
            representation_references_id=inputs["representation_references"]["id"],
            original_21_candidates_and_tokens_and_three_complete_packages_byte_unchanged=True,
            source_profiles_configs_and_original_generation_condition_byte_unchanged=True,
            original_W_false_and_null_distributions_not_rewritten=True,
            final_training_weights=None,
            student_utility=None,
            Contribution=None,
            VTDO_update=False,
            old_mainline="remains_paused",
            limitations=[
                "known single-task development source",
                "finite typed event interpretation, not general belief revision",
                "observed order is not internal causation",
                "class count is not Contribution",
                "class materialization must retain N/E prompt-source composition",
            ],
        )
        store = DurableStore(measurement)
        for projection in projections:
            store.json("projections/" + projection["label"] + ".json", projection)
        for name, value in (
            ("comparisons", pairs),
            ("distribution", distribution),
            ("assignments", distribution["assignments"]),
            ("classes", distribution["classes"]),
            ("controls", controls),
            ("execution_guards", guards),
            (
                "source_preservation",
                record(
                    "support_transition_preservation",
                    before_inventory_id=after["id"],
                    after_inventory_id=after["id"],
                    all_historical_bytes_identical=True,
                ),
            ),
            ("report", report),
        ):
            store.json(name + ".json", value)
        seal_directory(
            store,
            kind="support_transition_measurement_manifest",
            condition_id=condition["id"],
            report_id=report["id"],
        )
        return report
