"""Freeze source instances, measurement applicability and evaluation separation before calls."""

from pathlib import Path

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
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
from .guards import execution_guard, guard_report
from .plan import STAGE, configuration, freeze_condition, wiring_controls
from .preservation import history_inventory, preserved_sources
from .representation import representation_policy
from .rules import quotient_rule
from .source import contamination_registry, load_sources, selection_policy, source_report

ARTIFACT_PREFIX = "trusted_data_synthesis/artifacts/qa_vnext_cross_binding"
DESIGN_BYTES = 26_338
DESIGN_SHA256 = "469fbc90f41bc081db469a1a53ee82e9a2357b637a14b125a58b9352e1082a91"
DESIGN_PATH = Path(
    "/home/zhuxinrui/.codex/attachments/10c19857-74d3-4009-bf22-ef854f4afce4/pasted-text.txt"
)


def _target(root, output):
    root, output = root.resolve(), output.resolve()
    require(
        output.is_relative_to(root / ARTIFACT_PREFIX) and output != root / ARTIFACT_PREFIX,
        "cross_binding.additive_directory",
    )
    return root, output


def _population(root, implementation, policy, rule):
    sources = load_sources(root)
    adapters = [BoundShareTaskAdapter(source) for source in sources]
    condition, registrations, panel = freeze_condition(
        adapters, [source.binding_record for source in sources], implementation, policy, rule
    )
    return condition, registrations, panel, sources


def prepare(root: Path, output: Path):
    from .measurement import comparison_contract

    root, output = _target(root, output)
    directory = output / "preparation"
    require(not directory.exists(), "cross_binding.preparation_already_exists")
    with execution_guard(phase="preparation") as counts:
        design = DESIGN_PATH.read_bytes()
        require(
            len(design) == DESIGN_BYTES and sha(design) == DESIGN_SHA256,
            "cross_binding.audit_bytes",
        )
        implementation = source_snapshot(root)
        preserved, history = preserved_sources(root), history_inventory(root)
        binding = register_tokenizer(root)
        policy, rule = representation_policy(binding), quotient_rule()
        condition, registrations, panel, sources = _population(root, implementation, policy, rule)
        comparison = comparison_contract(condition, rule)
        controls, requests = wiring_controls(panel, condition, registrations)
        store = DurableStore(directory)
        store.write("experiment_design.txt", design)
        objects = {
            "implementation": implementation,
            "source_preservation": preserved,
            "history_inventory": history,
            "software": _software(),
            "tokenizer_binding": binding,
            "representation_policy": policy,
            "source_selection_policy": selection_policy(),
            "source_report": source_report(sources),
            "evaluation_separation": contamination_registry(sources),
            "condition": condition,
            "registrations": registrations,
            "protocol": contract(),
            "quotient_rule": rule,
            "comparison_contract": comparison,
            "controls": controls,
        }
        for name, value in objects.items():
            store.json(name + ".json", value)
        for label, request in requests.items():
            store.json("initial/" + label + "_request.json", request["public"])
            store.json("initial/" + label + "_http.json", request["http"])
        report = record(
            "cross_binding_preparation",
            stage=STAGE,
            condition_id=condition["id"],
            implementation_id=implementation["id"],
            source_commit=implementation["source_commit"],
            comparison_contract_id=comparison["id"],
            rule_id=rule["id"],
            source_report_id=objects["source_report"]["id"],
            evaluation_separation_id=objects["evaluation_separation"]["id"],
            session_registration_ids=[r["id"] for r in registrations],
            execution_directory=str(output / "execution"),
            prepared=True,
            frozen_before_credentials_or_provider_calls=True,
            provider_calls=0,
            task_count=len(sources),
            independent_evaluation_bound_and_ready=False,
        )
        store.json("report.json", report)
        store.json("execution_guards.json", guard_report(counts, phase="preparation"))
        seal_directory(
            store,
            kind="cross_binding_preparation_manifest",
            preparation_id=report["id"],
            condition_id=condition["id"],
        )
        return report


def prepared(root: Path, output: Path):
    from .measurement import comparison_contract

    root, output = _target(root, output)
    directory = output / "preparation"
    manifest = verify_directory(directory, kind="cross_binding_preparation_manifest")
    names = (
        "report",
        "implementation",
        "source_preservation",
        "history_inventory",
        "software",
        "tokenizer_binding",
        "representation_policy",
        "condition",
        "registrations",
        "quotient_rule",
        "comparison_contract",
        "controls",
        "source_report",
        "source_selection_policy",
        "evaluation_separation",
    )
    values = {name: read_json((directory / (name + ".json")).read_bytes()) for name in names}
    identity(values["report"], "cross_binding_preparation")
    verify_source_snapshot(root, values["implementation"])
    require(_software() == values["software"], "cross_binding.software_changed")
    require(
        preserved_sources(root) == values["source_preservation"]
        and history_inventory(root) == values["history_inventory"],
        "cross_binding.old_history_or_source_changed",
    )
    binding = register_tokenizer(root)
    require(
        binding == values["tokenizer_binding"]
        and representation_policy(binding) == values["representation_policy"]
        and quotient_rule() == values["quotient_rule"],
        "cross_binding.frozen_rule_or_representation_changed",
    )
    condition, registrations, panel, sources = _population(
        root, values["implementation"], values["representation_policy"], values["quotient_rule"]
    )
    require(
        canonical_json_bytes(condition) == canonical_json_bytes(values["condition"])
        and registrations == values["registrations"]
        and source_report(sources) == values["source_report"]
        and contamination_registry(sources) == values["evaluation_separation"]
        and selection_policy() == values["source_selection_policy"],
        "cross_binding.frozen_source_population_or_evaluation_policy",
    )
    require(
        comparison_contract(condition, values["quotient_rule"]) == values["comparison_contract"],
        "cross_binding.comparison_contract_changed",
    )
    checks, requests = wiring_controls(panel, condition, registrations)
    require(checks == values["controls"], "cross_binding.wiring_changed")
    for label, request in requests.items():
        for kind, item in (("request", request["public"]), ("http", request["http"])):
            require(
                (directory / f"initial/{label}_{kind}.json").read_bytes()
                == canonical_json_bytes(item),
                "cross_binding.initial_request_changed",
            )
    require(
        values["report"]["execution_directory"] == str(output / "execution")
        and manifest["condition_id"] == condition["id"],
        "cross_binding.execution_binding",
    )
    return {
        **values,
        "manifest": manifest,
        "panel": panel,
        "configurations": {name: configuration(name) for name in ("N", "E")},
    }
