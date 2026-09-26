"""Isolated routing for frozen financial/review logic after the 15-PDF repair.

Only execution roots, exact parent references and protocol provenance differ.
No original module globals or scientific predicates are patched. The sole old
source-review root guard is replaced by an equally strict new-root guard inside
an isolated function namespace; all other checks and coverage logic are reused.
"""

import argparse
import subprocess
import types
from pathlib import Path

import cross_market_layout_qualification_20260926 as financial
import cross_market_source_review_20260926 as review

base = financial.base
NEW = base.RAW / "original_evidence_revision_02"
GEOMETRY = NEW / "geometry_reconciled_01"
FINANCIAL = NEW / "financial_after_geometry_repair_01"
REVIEW = NEW / "source_review_after_geometry_repair_01"
REPAIR = NEW / "geometry_capacity_repair_01"
SCRIPT = "trusted_data_synthesis/scripts/cross_market_repaired_geometry_execution_20260926.py"
RECONCILIATION_SCRIPT = (
    "trusted_data_synthesis/scripts/cross_market_geometry_reconciliation_20260926.py"
)
REPAIR_SCRIPT = "trusted_data_synthesis/scripts/cross_market_geometry_capacity_repair_20260926.py"
FINANCIAL_KIND = "cross_market_layout_qualification_protocol"
REVIEW_KIND = "cross_market_source_review_protocol"


def require(condition, reason):
    base.require(condition, "repaired_execution." + reason)


def ref(path):
    path = Path(path)
    require(
        path.is_absolute() and path.resolve().is_relative_to(base.RAW.resolve()), "reference_root"
    )
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def isolated_namespace(module, **overrides):
    """Share immutable code objects, not the imported module's mutable globals."""
    namespace = dict(module.__dict__)
    namespace.update(overrides)
    for name, value in module.__dict__.items():
        if isinstance(value, types.FunctionType) and value.__module__ == module.__name__:
            cloned = types.FunctionType(
                value.__code__, namespace, name, value.__defaults__, value.__closure__
            )
            cloned.__kwdefaults__ = value.__kwdefaults__
            cloned.__annotations__ = dict(value.__annotations__)
            namespace[name] = cloned
    return namespace


def original_budgets_unspent():
    for root in (financial.RAW, review.RAW):
        require(not (root / "protocol.json").exists(), "old_downstream_protocol_already_registered")
        require(
            not any(root.glob("**/*attempt*.json")), "old_downstream_attempt_budget_already_spent"
        )
        require(
            not any((root / "documents").glob("*.json")), "old_downstream_results_already_exist"
        )
        require(
            not (root / "summary.json").exists() and not (root / "packet_manifest.json").exists(),
            "old_downstream_completion_already_exists",
        )


def validate_parent_records(repair, geometry, complete):
    require(
        repair["maximum_original_PDF_opens"] == 15
        and repair["maximum_attempts_per_PDF"] == 1
        and len(repair["documents"]) == 15,
        "exact_authorized_fifteen_repair_scope",
    )
    require(geometry.get("derived_geometry_view") is True, "explicit_derived_geometry_view")
    require(
        complete["protocol_id"] == geometry["id"]
        and complete["documents"] == 440
        and complete["coverage_pages"] == 104439
        and complete["selected_pages"] == 7530
        and complete["original_blank_pages_rendered"] == 420
        and complete["status"] == "GEOMETRY_COMPLETE_NOT_ADMITTED",
        "complete_reconciled_parent",
    )


def binding(root):
    """Small immutable provenance binding; no PDFs or financial enumeration."""
    original_budgets_unspent()
    repair_path = REPAIR / "protocol.json"
    repair = base.checked(base.read(repair_path), "cross_market_geometry_capacity_repair_protocol")
    geometry = base.checked(
        base.read(GEOMETRY / "protocol.json"), "cross_market_original_geometry_protocol"
    )
    complete = base.checked(
        base.read(GEOMETRY / "summary.json"), "cross_market_original_geometry_completed"
    )
    validate_parent_records(repair, geometry, complete)
    parents = geometry["parent_references"]
    require(
        set(parents)
        == {
            "original_protocol",
            "original_completion",
            "encoding_protocol",
            "encoding_completion",
            "capacity_protocol",
            "capacity_completion",
        },
        "exact_reconciliation_provenance_routes",
    )
    for reference in parents.values():
        require(ref(Path(reference["path"])) == reference, "reconciliation_parent_bytes")
    require(
        parents["capacity_protocol"] == ref(repair_path)
        and parents["capacity_completion"] == ref(REPAIR / "summary.json"),
        "exact_capacity_authorization_and_completion",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(geometry["sources"])
    for name in (
        *sources,
        SCRIPT,
        RECONCILIATION_SCRIPT,
        REPAIR_SCRIPT,
        financial.SCRIPT,
        review.SCRIPT,
    ):
        payload = (root / name).read_bytes()
        require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "committed_adapter_and_parent_code:" + name,
        )
        digest = base.sha(payload)
        require(name not in sources or sources[name] == digest, "reconciled_parent_source_hash")
        sources[name] = digest
    return dict(
        adapter="frozen_layout_and_review_isolated_root_adapter.v1",
        sources=sources,
        original_financial_root=str(financial.RAW),
        original_source_review_root=str(review.RAW),
        financial_root=str(FINANCIAL),
        source_review_root=str(REVIEW),
        geometry_root=str(GEOMETRY),
        repair_authorization_protocol=ref(repair_path),
        repair_completion=ref(REPAIR / "summary.json"),
        reconciled_geometry_protocol=ref(GEOMETRY / "protocol.json"),
        reconciled_geometry_completion=ref(GEOMETRY / "summary.json"),
        reconciliation_parent_references=parents,
        prior_unexecuted_financial_budget_relocated_not_extended=True,
        maximum_financial_cached_document_passes=440,
        maximum_rederived_observations=19026,
        maximum_task_enumerations=1,
        maximum_source_review_packet_plans=1,
        original_PDF_opens=0,
        parser_calls=0,
        model_calls=0,
        network_requests=0,
        scientific_logic_changed=False,
        source_review_semantically_passed=False,
    )


def bind_protocol(value, kind, execution_binding):
    base.checked(value, kind)
    body = {k: v for k, v in value.items() if k not in {"id", "schema_version"}}
    sources = dict(body.get("sources", {}))
    for name, digest in execution_binding["sources"].items():
        require(name not in sources or sources[name] == digest, "source_hash_conflict")
        sources[name] = digest
    body.update(sources=sources, execution_adapter=execution_binding)
    augmented = base.record(kind, **body)
    # This is a newly constructed, not-yet-written protocol. Updating it before
    # save also makes the frozen caller retain the correct augmented protocol ID.
    value.clear()
    value.update(augmented)
    return value


def validate_binding(value, kind, expected):
    base.checked(value, kind)
    require(value.get("execution_adapter") == expected, "exact_frozen_execution_binding")
    require(
        all(
            value.get("sources", {}).get(name) == digest
            for name, digest in expected["sources"].items()
        ),
        "all_adapter_sources_bound",
    )
    return value


def protocol_save(namespace, destination, kind, execution_binding):
    original_save = namespace["save"]

    def save(path, value):
        if Path(path).resolve() == (destination / "protocol.json").resolve():
            bind_protocol(value, kind, execution_binding)
        return original_save(path, value)

    return save


def financial_namespace(root, execution_binding=None):
    execution_binding = execution_binding or binding(root)
    namespace = isolated_namespace(financial, RAW=FINANCIAL, GEOMETRY=GEOMETRY)
    original_protocol = namespace["protocol"]

    def protocol(project_root):
        value = original_protocol(project_root)
        return validate_binding(value, FINANCIAL_KIND, execution_binding)

    namespace["save"] = protocol_save(namespace, FINANCIAL, FINANCIAL_KIND, execution_binding)
    namespace["protocol"] = protocol
    return namespace


def review_namespace(root, execution_binding=None):
    execution_binding = execution_binding or binding(root)
    namespace = isolated_namespace(review, RAW=REVIEW)
    original_require = namespace["require"]

    def review_require(condition, reason):
        if reason == "this_bounded_supplement_inputs_only":
            # prepare_review below already checks its exact concrete arguments.
            # This replaces only the frozen assumption that roots are named
            # literally geometry/financial. All semantic and coverage checks
            # keep their original predicates and original failure behavior.
            return original_require(namespace.get("validated_repaired_input_roots") is True, reason)
        return original_require(condition, reason)

    namespace["require"] = review_require
    namespace["save"] = protocol_save(namespace, REVIEW, REVIEW_KIND, execution_binding)
    return namespace


def register_financial(root):
    execution_binding = binding(root)
    namespace = financial_namespace(root, execution_binding)
    value = namespace["register"](root)
    return validate_binding(value, FINANCIAL_KIND, execution_binding)


def run_financial(root):
    namespace = financial_namespace(root)
    return namespace["run"](root)


def prepare_review(root, financial_root=FINANCIAL, geometry_root=GEOMETRY):
    require(
        financial_root.resolve() == FINANCIAL.resolve()
        and geometry_root.resolve() == GEOMETRY.resolve(),
        "only_exact_repaired_financial_and_geometry_roots",
    )
    execution_binding = binding(root)
    financial_namespace(root, execution_binding)["protocol"](root)
    existing = REVIEW / "protocol.json"
    if existing.exists():
        validate_binding(base.read(existing), REVIEW_KIND, execution_binding)
    namespace = review_namespace(root, execution_binding)
    namespace["validated_repaired_input_roots"] = True
    result = namespace["prepare"](root, financial_root, geometry_root)
    plan = validate_binding(base.read(existing), REVIEW_KIND, execution_binding)
    require(result["protocol_id"] == plan["id"], "packet_manifest_augmented_protocol_parent")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("register-financial", "run-financial", "prepare-review"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    actions = {
        "register-financial": register_financial,
        "run-financial": run_financial,
        "prepare-review": prepare_review,
    }
    value = actions[args.action](args.root.resolve())
    base.emit(
        dict(event="repaired_geometry_" + args.action, id=value["id"], status=value.get("status"))
    )


if __name__ == "__main__":
    main()
