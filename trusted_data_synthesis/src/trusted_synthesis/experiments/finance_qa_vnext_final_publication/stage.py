"""Freeze explicit Final publication and six new complete tasks; never resume old states."""

from pathlib import Path

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import (
    public_final_contract,
    public_final_schema,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore

from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require, sha
from ..finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_directory,
    verify_source_snapshot,
)
from ..finance_qa_vnext_model_execution.representation import register_tokenizer
from ..finance_qa_vnext_model_execution.runner import _software
from .controls import run_controls
from .guards import execution_guard, guard_report
from .measurement import comparison_contract, measurement_application
from .plan import STAGE, configuration, freeze_condition, wiring_controls
from .preservation import history_inventory, preserved_sources
from .representation import representation_policy
from .rules import quotient_rule
from .source import load_inputs

ARTIFACT_PREFIX = "trusted_data_synthesis/artifacts/qa_vnext_final_publication"
DESIGN_BYTES = 21_273
DESIGN_SHA256 = "b6a8b424d0cb6f2505a2b2a1af99a8960e1b51a6acfb92d6d2f9752ff4e37a6b"
DESIGN_PATH = Path(
    "/home/zhuxinrui/.codex/attachments/91dc6809-3d52-41d9-88b3-8c4eafc076de/pasted-text.txt"
)


def _target(root, output):
    root, output = root.resolve(), output.resolve()
    require(
        output.is_relative_to(root / ARTIFACT_PREFIX) and output != root / ARTIFACT_PREFIX,
        "final_publication.additive_directory",
    )
    return root, output


def _population(inputs, implementation, policy, rule):
    groups = ("T01", "T02", "T03")
    return freeze_condition(
        [inputs["adapters"][group] for group in groups],
        [inputs["sources"][group].binding_record for group in groups],
        implementation,
        policy,
        rule,
    )


def prepare(root: Path, output: Path):
    root, output = _target(root, output)
    directory = output / "preparation"
    require(not directory.exists(), "final_publication.preparation_already_exists")
    with execution_guard(phase="preparation") as counts:
        design = DESIGN_PATH.read_bytes()
        require(
            len(design) == DESIGN_BYTES and sha(design) == DESIGN_SHA256,
            "final_publication.audit_bytes",
        )
        implementation = source_snapshot(root)
        preserved, history = preserved_sources(root), history_inventory(root)
        inputs = load_inputs(root)
        controls = run_controls(inputs)
        require(controls["all_expected_outcomes"], "final_publication.readonly_controls_failed")
        binding = register_tokenizer(root)
        policy, rule = representation_policy(binding), quotient_rule()
        condition, registrations, panel = _population(inputs, implementation, policy, rule)
        comparison = comparison_contract(condition, rule)
        wiring, requests = wiring_controls(panel, condition, registrations)
        store = DurableStore(directory)
        store.write("experiment_design.txt", design)
        objects = {
            "implementation": implementation,
            "source_preservation": preserved,
            "history_inventory": history,
            "software": _software(),
            "tokenizer_binding": binding,
            "representation_policy": policy,
            "source_checks": inputs["source_checks"],
            "source_report": inputs["source_report"],
            "evaluation_separation": inputs["evaluation_policy"],
            "old_condition": inputs["old_condition"],
            "readonly_ready_states": inputs["ready_states"],
            "readonly_controls": controls,
            "condition": condition,
            "registrations": registrations,
            "protocol": contract(),
            "quotient_rule": rule,
            "measurement_application": measurement_application(),
            "public_final_contract": public_final_contract(),
            "public_final_schema": public_final_schema(),
            "comparison_contract": comparison,
            "controls": wiring,
        }
        for name, value in objects.items():
            store.json(name + ".json", value)
        for label, request in requests.items():
            store.json("initial/" + label + "_request.json", request["public"])
            store.json("initial/" + label + "_http.json", request["http"])
        report = record(
            "final_publication_preparation",
            stage=STAGE,
            condition_id=condition["id"],
            implementation_id=implementation["id"],
            source_commit=implementation["source_commit"],
            comparison_contract_id=comparison["id"],
            rule_id=rule["id"],
            measurement_application_id=measurement_application()["id"],
            public_final_contract_id=public_final_contract()["id"],
            readonly_controls_id=controls["id"],
            source_checks_id=inputs["source_checks"]["id"],
            session_registration_ids=[row["id"] for row in registrations],
            execution_directory=str(output / "execution"),
            prepared=True,
            frozen_before_credentials_or_provider_calls=True,
            provider_calls=0,
            readonly_controls_are_model_successes=False,
            historical_0_of_12_unchanged=True,
            independent_evaluation_bound_and_ready=False,
        )
        store.json("report.json", report)
        store.json("execution_guards.json", guard_report(counts, phase="preparation"))
        seal_directory(
            store,
            kind="final_publication_preparation_manifest",
            preparation_id=report["id"],
            condition_id=condition["id"],
        )
        return report


def prepared(root: Path, output: Path):
    root, output = _target(root, output)
    directory = output / "preparation"
    manifest = verify_directory(directory, kind="final_publication_preparation_manifest")
    names = (
        "report",
        "implementation",
        "source_preservation",
        "history_inventory",
        "software",
        "tokenizer_binding",
        "representation_policy",
        "source_checks",
        "source_report",
        "evaluation_separation",
        "old_condition",
        "readonly_ready_states",
        "readonly_controls",
        "condition",
        "registrations",
        "protocol",
        "quotient_rule",
        "measurement_application",
        "public_final_contract",
        "public_final_schema",
        "comparison_contract",
        "controls",
    )
    values = {name: read_json((directory / (name + ".json")).read_bytes()) for name in names}
    identity(values["report"], "final_publication_preparation")
    verify_source_snapshot(root, values["implementation"])
    require(_software() == values["software"], "final_publication.software_changed")
    require(
        preserved_sources(root) == values["source_preservation"]
        and history_inventory(root) == values["history_inventory"],
        "final_publication.old_artifacts_or_protected_logic_changed",
    )
    inputs = load_inputs(root)
    require(
        inputs["source_checks"] == values["source_checks"]
        and inputs["source_report"] == values["source_report"]
        and inputs["old_condition"] == values["old_condition"]
        and inputs["evaluation_policy"] == values["evaluation_separation"]
        and inputs["ready_states"] == values["readonly_ready_states"],
        "final_publication.frozen_inputs_changed",
    )
    # Read the sealed controls, do not execute the twelve-state verifier controls a second time.
    require(
        values["readonly_controls"]["all_expected_outcomes"]
        and values["readonly_controls"]["id"] == values["report"]["readonly_controls_id"],
        "final_publication.saved_readonly_controls",
    )
    binding = register_tokenizer(root)
    require(
        binding == values["tokenizer_binding"]
        and representation_policy(binding) == values["representation_policy"]
        and quotient_rule() == values["quotient_rule"]
        and measurement_application() == values["measurement_application"]
        and public_final_contract() == values["public_final_contract"]
        and public_final_schema() == values["public_final_schema"],
        "final_publication.publication_rule_or_representation_drift",
    )
    condition, registrations, panel = _population(
        inputs, values["implementation"], values["representation_policy"], values["quotient_rule"]
    )
    require(
        canonical_json_bytes(condition) == canonical_json_bytes(values["condition"])
        and registrations == values["registrations"],
        "final_publication.frozen_population_changed",
    )
    require(
        comparison_contract(condition, values["quotient_rule"]) == values["comparison_contract"],
        "final_publication.comparison_contract_drift",
    )
    checks, requests = wiring_controls(panel, condition, registrations)
    require(checks == values["controls"], "final_publication.wiring_changed")
    for label, request in requests.items():
        for kind, item in (("request", request["public"]), ("http", request["http"])):
            require(
                (directory / f"initial/{label}_{kind}.json").read_bytes()
                == canonical_json_bytes(item),
                "final_publication.initial_request_drift",
            )
    require(
        values["report"]["execution_directory"] == str(output / "execution")
        and manifest["condition_id"] == condition["id"],
        "final_publication.execution_binding",
    )
    return {
        **values,
        "manifest": manifest,
        "panel": panel,
        "configurations": {profile: configuration(profile) for profile in ("N", "E")},
    }
