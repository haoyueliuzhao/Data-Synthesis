"""Freeze exact new profiles/population and existing Share semantics before credentials or calls."""

from pathlib import Path

from trusted_synthesis.canonical_json import canonical_json_bytes
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
from ..finance_qa_vnext_panel_quotient.rules import quotient_rule
from ..finance_qa_vnext_task_panel.representation import representation_policy
from .guards import execution_guard, guard_report
from .plan import STAGE, configuration, freeze_condition, wiring_controls
from .source import history_inventory, preserved_sources

ARTIFACT_PREFIX = "trusted_data_synthesis/artifacts/qa_vnext_support_exploration"
DESIGN_BYTES = 25_733
DESIGN_SHA256 = "64524dee1a519236d9e3fc69e525fedb43b555f081390d0dac962c70f5ed35d3"
DESIGN_PATH = Path(
    "/home/zhuxinrui/.codex/attachments/95594c7e-cf52-4c23-bbc6-d9f02e4ca667/pasted-text.txt"
)


def _target(root, output):
    root, output = root.resolve(), output.resolve()
    require(
        output.is_relative_to(root / ARTIFACT_PREFIX) and output != root / ARTIFACT_PREFIX,
        "support_exploration.additive_directory",
    )
    return root, output


def prepare(root: Path, output: Path):
    root, output = _target(root, output)
    directory = output / "preparation"
    require(not directory.exists(), "support_exploration.preparation_already_exists")
    with execution_guard(phase="preparation") as counts:
        design = DESIGN_PATH.read_bytes()
        require(
            len(design) == DESIGN_BYTES and sha(design) == DESIGN_SHA256,
            "support_exploration.audit_bytes",
        )
        implementation = source_snapshot(root)
        preserved = preserved_sources(root)
        history = history_inventory(root)
        binding = register_tokenizer(root)
        policy = representation_policy(binding)
        condition, registrations, panel = freeze_condition(root, implementation, policy)
        from .quotient import comparison_contract

        rule = quotient_rule()
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
            "condition": condition,
            "registrations": registrations,
            "catalog": panel.catalog.descriptor,
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
            "support_exploration_preparation",
            stage=STAGE,
            condition_id=condition["id"],
            implementation_id=implementation["id"],
            comparison_contract_id=comparison["id"],
            rule_id=rule["id"],
            session_registration_ids=[r["id"] for r in registrations],
            execution_directory=str(output / "execution"),
            prepared=True,
            frozen_before_credentials_or_provider_calls=True,
            provider_calls=0,
        )
        store.json("report.json", report)
        store.json("execution_guards.json", guard_report(counts, phase="preparation"))
        seal_directory(
            store,
            kind="support_exploration_preparation_manifest",
            preparation_id=report["id"],
            condition_id=condition["id"],
        )
        return report


def prepared(root: Path, output: Path):
    root, output = _target(root, output)
    directory = output / "preparation"
    manifest = verify_directory(directory, kind="support_exploration_preparation_manifest")
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
    )
    values = {name: read_json((directory / (name + ".json")).read_bytes()) for name in names}
    identity(values["report"], "support_exploration_preparation")
    verify_source_snapshot(root, values["implementation"])
    require(_software() == values["software"], "support_exploration.software_changed")
    require(
        preserved_sources(root) == values["source_preservation"]
        and history_inventory(root) == values["history_inventory"],
        "support_exploration.old_history_or_source_changed",
    )
    require(values["quotient_rule"] == quotient_rule(), "support_exploration.quotient_rule_changed")
    binding = register_tokenizer(root)
    require(
        binding == values["tokenizer_binding"]
        and representation_policy(binding) == values["representation_policy"],
        "support_exploration.tokenizer_policy_changed",
    )
    condition, registrations, panel = freeze_condition(
        root, values["implementation"], values["representation_policy"]
    )
    require(
        condition == values["condition"] and registrations == values["registrations"],
        "support_exploration.frozen_generation_source",
    )
    from .quotient import comparison_contract

    require(
        comparison_contract(condition, values["quotient_rule"]) == values["comparison_contract"],
        "support_exploration.comparison_contract_changed",
    )
    checks, requests = wiring_controls(panel, condition, registrations)
    require(checks == values["controls"], "support_exploration.wiring_changed")
    for label, request in requests.items():
        for kind, item in (("request", request["public"]), ("http", request["http"])):
            require(
                (directory / f"initial/{label}_{kind}.json").read_bytes()
                == canonical_json_bytes(item),
                "support_exploration.initial_request_changed",
            )
    require(
        values["report"]["execution_directory"] == str(output / "execution")
        and manifest["condition_id"] == condition["id"],
        "support_exploration.execution_binding",
    )
    return {
        **values,
        "manifest": manifest,
        "panel": panel,
        "configurations": {name: configuration(name) for name in ("N", "E")},
    }
