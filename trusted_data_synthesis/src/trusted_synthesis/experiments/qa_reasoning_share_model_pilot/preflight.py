"""One zero-network preparation followed by six non-replaceable model sessions."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    source_group,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol import models as parent_models
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import initial_dynamic
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.public_view import (
    make_state,
    public_context,
    request_for,
)

from . import models
from .adapter import DeepSeekAdapter, MockTransport, render_http_request
from .controls import CONTROL_NAMES, Scenario, control_declaration
from .engine import ModelProtocolEngine
from .independent import aggregate_pilot, audit_session
from .models import model_config, record, require, sha

SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/"
    + name
    for name in (
        "__init__.py",
        "models.py",
        "adapter.py",
        "engine.py",
        "controls.py",
        "independent.py",
        "preflight.py",
    )
)
REFERENCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/" + name
    for name in (
        "canonical_json.py",
        "experiments/qa_reasoning_finite_comparison/inputs.py",
        "experiments/qa_reasoning_fixed_fixture/runtime.py",
        "experiments/qa_reasoning_part_whole_share/models.py",
        "experiments/qa_reasoning_part_whole_share/runtime.py",
        "experiments/qa_reasoning_share_public_protocol/models.py",
        "experiments/qa_reasoning_share_public_protocol/public_view.py",
        "experiments/qa_reasoning_share_public_protocol/engine.py",
        "experiments/qa_reasoning_share_public_protocol/fixture.py",
        "core/operations/registry.py",
        "core/operations/executors/numeric.py",
        "domains/finance/operations.py",
    )
)


def read_json(root: Path, name: str) -> dict[str, Any]:
    return json.loads((root / name).read_bytes())


def _frozen_inputs(root: Path) -> dict[str, Any]:
    parent = files_at(root / models.PARENT)
    validate_manifest(parent, models.PARENT_MANIFEST, models.PARENT_ROOT)
    require(
        len(parent) == 71 and sum(map(len, parent.values())) == 648_048, "pilot.parent_geometry"
    )
    original = files_at(root / parent_models.PARENT)
    validate_manifest(original, parent_models.PARENT_MANIFEST, parent_models.PARENT_ROOT)
    require(
        len(original) == 65 and sum(map(len, original.values())) == 254_479, "pilot.source_geometry"
    )
    source, legacy = (json.loads(original[p]) for p in ("source_binding.json", "contract.json"))
    context = public_context(source, legacy)
    require(context == json.loads(parent["public_context.json"]), "pilot.identical_public_context")
    return {
        "parent": parent,
        "original": original,
        "source": source,
        "legacy": legacy,
        "context": context,
        "parent_protocol": json.loads(parent["protocol_contract.json"]),
    }


def _parent_unchanged(root: Path, frozen: dict[str, Any]) -> None:
    require(files_at(root / models.PARENT) == frozen["parent"], "pilot.parent_changed")
    require(files_at(root / parent_models.PARENT) == frozen["original"], "pilot.source_changed")


def _authorize(review: bytes, config: dict[str, Any]) -> dict[str, Any]:
    require(
        len(review) == models.REVIEW_BYTES and sha(review) == models.REVIEW_SHA256,
        "pilot.review_authority",
    )
    return record(
        "authorization",
        stage=models.STAGE,
        review_sha256=sha(review),
        review_bytes=len(review),
        current_operator_directive=models.DIRECTIVE,
        current_operator_directive_bytes=len(models.DIRECTIVE.encode()),
        current_operator_directive_sha256=sha(models.DIRECTIVE.encode()),
        online_authority=(
            "current instruction to conduct this pilot plus standing explicit "
            "project API authorization"
        ),
        external_review_itself_is_online_authorization=False,
        model_configuration_id=config["id"],
        online_sessions=6,
        provider_attempt_limits={"per_session": 12, "pilot": 72},
        complete_local_mock_sessions=2,
        single_turn_local_failure_controls=2,
        local_mock_callback_cap=14,
        local_kernel_call_cap=5,
        online_kernel_call_cap=18,
        automatic_retries=0,
        replacement_sessions=0,
        outcome_conditioned_extra_calls=False,
        old_candidate_runtime_calls=0,
        source_rescans=0,
        new_quotient_comparisons=0,
        GPU_jobs=0,
        training_release_or_old_mainline_restart=False,
        old_mainline="remains_paused",
    )


def _members(root: Path) -> list[dict[str, Any]]:
    return [
        {"relative_path": p, "sha256": sha(data), "byte_count": len(data)}
        for p, data in sorted(files_at(root).items())
    ]


def _verify_subset(root: Path, manifest: dict[str, Any]) -> None:
    require(
        manifest["id"]
        == record(
            "preparation_manifest",
            **{k: v for k, v in manifest.items() if k not in {"id", "schema_version"}},
        )["id"],
        "pilot.preparation_identity",
    )
    paths = [member["relative_path"] for member in manifest["members"]]
    require(
        len(paths) == len(set(paths))
        and all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in paths),
        "pilot.preparation_member_paths",
    )
    for member in manifest["members"]:
        data = (root / member["relative_path"]).read_bytes()
        require(
            len(data) == member["byte_count"] and sha(data) == member["sha256"],
            "pilot.preparation_bytes",
        )


def _manifest(writer: DurableArtifactWriter, report: dict[str, Any]) -> dict[str, Any]:
    members = _members(writer.root)
    body = {
        "schema_version": "share_model_pilot_manifest.v1",
        "members": members,
        "member_count": len(members),
        "member_bytes": sum(m["byte_count"] for m in members),
        "report_id": report["id"],
        "self_excluding": True,
        "artifact_root": strict_canonical_hash(members, prefix="share_model_pilot_root:"),
    }
    manifest = {
        **body,
        "manifest_id": strict_canonical_hash(body, prefix="share_model_pilot_manifest:"),
    }
    writer.write_json("artifact_manifest.json", manifest)
    validate_manifest(files_at(writer.root), manifest["manifest_id"], manifest["artifact_root"])
    return manifest


def _audit(
    frozen: dict[str, Any],
    protocol: dict[str, Any],
    config: dict[str, Any],
    binding: dict[str, Any],
    declaration: dict[str, Any],
    session_root: Path,
) -> dict[str, Any]:
    return audit_session(
        context=frozen["context"],
        protocol=protocol,
        source=frozen["source"],
        legacy_contract=frozen["legacy"],
        adapter_binding=binding,
        model_config=config,
        session_registration=declaration,
        session_root=session_root,
    )


def prepare_pilot(
    *,
    repo_root: Path,
    external_audit: Path,
    source_commit: str,
    source_tree: str,
    output_directory: Path,
) -> dict[str, Any]:
    root = repo_root.resolve()
    frozen = _frozen_inputs(root)
    config = model_config()
    protocol = models.protocol_contract(frozen["parent_protocol"], config)
    review = external_audit.read_bytes()
    authorization = _authorize(review, config)
    source_authority = record(
        "source_authority",
        implementation=source_group(root, source_commit, source_tree, SOURCE_PATHS),
        declared_references=source_group(
            root, models.PARENT_SOURCE_COMMIT, models.PARENT_SOURCE_TREE, REFERENCE_PATHS
        ),
        complete_transitive_or_runtime_environment_closure_claimed=False,
    )
    adapter = DeepSeekAdapter(config)
    declarations = models.session_declarations(protocol, config)
    controls = [control_declaration(name, protocol, config) for name in CONTROL_NAMES]
    registration = record(
        "pilot_registration",
        authorization_id=authorization["id"],
        source_authority_id=source_authority["id"],
        public_context_id=frozen["context"]["id"],
        protocol_id=protocol["id"],
        model_configuration_id=config["id"],
        adapter_binding_id=adapter.binding["id"],
        session_ids=[d["id"] for d in declarations],
        sessions=declarations,
        control_session_ids=[d["id"] for d in controls],
        fixed_online_denominator=6,
        maximum_online_provider_attempts=72,
        success_is_not_a_workflow_requirement=True,
        both_support_routes_are_not_a_requirement=True,
        never_replace_or_add_sessions=True,
        before_first_online_attempt=True,
    )
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    writer.write_bytes("external_review.txt", review)
    writer.write_bytes("operator_directive.txt", models.DIRECTIVE.encode())
    for name, obj in (
        ("authorization", authorization),
        ("source_authority", source_authority),
        ("model_config", config),
        ("public_context", frozen["context"]),
        ("protocol_contract", protocol),
        ("model_adapter_binding", adapter.binding),
        ("pilot_registration", registration),
    ):
        writer.write_json(name + ".json", obj)
    writer.write_json(
        "parent_freeze.json",
        record(
            "parent_freeze",
            protocol_directory=models.PARENT,
            protocol_manifest=models.PARENT_MANIFEST,
            protocol_root=models.PARENT_ROOT,
            protocol_files=71,
            protocol_bytes=648_048,
            source_directory=parent_models.PARENT,
            source_manifest=parent_models.PARENT_MANIFEST,
            source_root=parent_models.PARENT_ROOT,
            source_files=65,
            source_bytes=254_479,
            old_W_share=1,
            old_finite_classes=2,
            older_compound_task_W=None,
            old_result_recomputed=False,
        ),
    )
    for declaration in declarations:
        writer.write_json("declarations/" + declaration["label"] + ".json", declaration)
    initial = make_state(frozen["context"], protocol, initial_dynamic())
    dry_request = render_http_request(
        request_for(initial, protocol),
        config,
        session_id=declarations[0]["id"],
        turn_index=0,
        call_id="zero_network_render_probe",
    )
    writer.write_json(
        "initial_request_size_check.json",
        record(
            "request_size_check",
            provider_request=dry_request,
            actual_serialized_request_bytes=dry_request["body_byte_count"],
            input_token_conservative_bound=dry_request["input_token_upper_bound"],
            exact_token_count=None,
            reserved_completion_tokens=config["max_tokens"],
            public_output_byte_limit=config["maximum_public_response_bytes"],
            bytes_are_not_exact_tokens=True,
            Provider_attempts=0,
            credential_reads=0,
        ),
    )
    writer.write_json(
        "pre_control_registration_receipt.json",
        record(
            "registration_receipt",
            pilot_registration_id=registration["id"],
            all_six_sessions_registered_before_online=True,
            source_authority_id=source_authority["id"],
            write_events=list(writer.events),
            Provider_attempts=0,
            credential_reads=0,
            no_replace=True,
        ),
    )
    control_reports = []
    for declaration, name in zip(controls, CONTROL_NAMES, strict=True):
        scenario = Scenario(name)
        mock = DeepSeekAdapter(config, transport=MockTransport(scenario.handle))
        writer.write_json("control_declarations/" + name + ".json", declaration)
        writer.write_json("control_bindings/" + name + ".json", mock.binding)
        session_root = writer.root / "controls" / name
        engine = ModelProtocolEngine(
            context=frozen["context"],
            protocol=protocol,
            source=frozen["source"],
            legacy_contract=frozen["legacy"],
            adapter_binding=mock.binding,
            model_config=config,
            session_registration=declaration,
            output_directory=session_root,
        )
        while (
            engine.current_state()["phase"] != "terminal"
            and len(engine.events) < declaration["maximum_mock_callbacks"]
        ):
            engine.exchange(mock)
        engine.finish()
        audit = _audit(frozen, protocol, config, mock.binding, declaration, session_root)
        state = engine.current_state()
        if name in {"direct", "reject_then_direct"}:
            passed = (
                audit["qualified"] is True
                and len(engine.events) == declaration["maximum_mock_callbacks"]
                and engine.kernel_calls == declaration["maximum_action_dispatches"]
            )
        elif name == "invalid_json":
            passed = (
                len(engine.events) == 1
                and engine.kernel_calls == 0
                and state["phase"] == "action"
                and state["submission_count"] == 1
                and engine.events[0]["submission"]["raw_public_json"] is None
                and engine.events[0]["receipt"]["admitted"] is False
            )
        else:
            passed = (
                len(engine.attempts) == 1
                and engine.kernel_calls == 0
                and state["terminal"] == "transport.timeout"
                and state["submission_count"] == 0
                and engine.events[0]["submission"] is None
            )
        if name == "reject_then_direct":
            reject_event = engine.events[1]
            passed = (
                passed
                and reject_event["claim"] is None
                and reject_event["post_state"]["accepted_claims"] == []
                and reject_event["post_state"]["pending_observation"] is None
                and engine.events[2]["execution"]["inputs"][1]["ref_id"]
                == frozen["source"]["evidence"]["total"]["id"]
            )
        result = record(
            "control_result",
            name=name,
            session_id=declaration["id"],
            passed=passed,
            complete_control=declaration["complete_session_control"],
            mock_callbacks=len(engine.attempts),
            kernel_calls=engine.kernel_calls,
            Provider_attempts=0,
            independent_validation=audit,
            state_id=state["id"],
            model_behavior=False,
        )
        writer.write_json("control_results/" + name + ".json", result)
        control_reports.append(result)
    _parent_unchanged(root, frozen)
    preparation = record(
        "preparation_report",
        status="ready_for_registered_online_pilot"
        if all(r["passed"] for r in control_reports)
        else "local_control_failed_stop_before_online",
        pilot_registration_id=registration["id"],
        source_authority_id=source_authority["id"],
        controls=control_reports,
        all_controls_passed=all(r["passed"] for r in control_reports),
        mock_callbacks=sum(r["mock_callbacks"] for r in control_reports),
        mock_kernel_calls=sum(r["kernel_calls"] for r in control_reports),
        Provider_attempts=0,
        credential_reads=0,
        online_sessions_started=0,
        model_reachability=None,
        old_mainline="remains_paused",
    )
    writer.write_json("preparation_report.json", preparation)
    manifest = record(
        "preparation_manifest",
        members=_members(writer.root),
        preparation_report_id=preparation["id"],
        self_excluding=True,
    )
    writer.write_json("preparation_manifest.json", manifest)
    return preparation


def _credential(path: Path) -> str:
    # Explicit one-time .env read after zero-network preparation. Never shell-source it.
    values = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == "DEEPSEEK_API_KEY":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            values.append(value)
    require(len(values) == 1 and bool(values[0]), "pilot.credential_unavailable")
    return values[0]


def run_online(*, repo_root: Path, output_directory: Path, credential_path: Path) -> dict[str, Any]:
    root, out = repo_root.resolve(), output_directory.resolve()
    frozen = _frozen_inputs(root)
    preparation_manifest = read_json(out, "preparation_manifest.json")
    _verify_subset(out, preparation_manifest)
    preparation = read_json(out, "preparation_report.json")
    require(preparation["all_controls_passed"], "pilot.local_controls_not_passed")
    require(
        not (out / "online_start_receipt.json").exists(), "pilot.no_online_restart_or_replacement"
    )
    config, protocol, binding, registration, authority = (
        read_json(out, name + ".json")
        for name in (
            "model_config",
            "protocol_contract",
            "model_adapter_binding",
            "pilot_registration",
            "source_authority",
        )
    )
    require(
        config == model_config()
        and protocol == models.protocol_contract(frozen["parent_protocol"], config),
        "pilot.frozen_online_configuration",
    )
    implementation = authority["implementation"]
    require(
        source_group(root, implementation["commit"], implementation["tree"], SOURCE_PATHS)
        == implementation,
        "pilot.source_changed_after_preparation",
    )
    require(DeepSeekAdapter(config).binding == binding, "pilot.adapter_binding_changed")
    require(
        read_json(out, "authorization.json")
        == _authorize((out / "external_review.txt").read_bytes(), config)
        and (out / "operator_directive.txt").read_bytes() == models.DIRECTIVE.encode()
        and registration["sessions"] == models.session_declarations(protocol, config)
        and registration["session_ids"] == [d["id"] for d in registration["sessions"]],
        "pilot.exact_current_authority_and_six_sessions",
    )
    api_key = _credential(credential_path)
    writer = DurableArtifactWriter(out)
    writer.write_json(
        "online_start_receipt.json",
        record(
            "online_start_receipt",
            pilot_registration_id=registration["id"],
            preparation_manifest_id=preparation_manifest["id"],
            model_configuration_id=config["id"],
            all_six_sessions_predeclared=True,
            maximum_provider_attempts=72,
            per_session_preallocated_attempts=12,
            automatic_retries=0,
            replacement_sessions=0,
            credential_file_reads=1,
            credential_content_or_hash_persisted=False,
            before_any_online_send=True,
        ),
    )

    def run(declaration: dict[str, Any]) -> dict[str, Any]:
        adapter = DeepSeekAdapter(config)
        session_root = out / "online" / declaration["label"]
        engine = ModelProtocolEngine(
            context=frozen["context"],
            protocol=protocol,
            source=frozen["source"],
            legacy_contract=frozen["legacy"],
            adapter_binding=binding,
            model_config=config,
            session_registration=declaration,
            output_directory=session_root,
        )
        try:
            while engine.current_state()["phase"] != "terminal":
                engine.exchange(adapter, api_key=api_key)
        except Exception as error:
            engine.writer.write_json(
                "engine_failure.json",
                record(
                    "engine_failure",
                    session_id=declaration["id"],
                    failure_type=type(error).__name__,
                    stage=getattr(error, "stage", "pilot.unclassified_engine_failure"),
                    private_error_text_persisted=False,
                    no_retry=True,
                    no_replacement=True,
                ),
            )
        engine.finish()
        return _audit(frozen, protocol, config, binding, declaration, session_root)

    with concurrent.futures.ThreadPoolExecutor(max_workers=config["session_parallelism"]) as pool:
        reports = list(pool.map(run, registration["sessions"]))
    _parent_unchanged(root, frozen)
    return _finalize(writer, preparation, config, registration, authority, reports)


def _finalize(
    writer: DurableArtifactWriter,
    preparation: dict[str, Any],
    config: dict[str, Any],
    registration: dict[str, Any],
    authority: dict[str, Any],
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    for declaration, report in zip(registration["sessions"], reports, strict=True):
        writer.write_json("online_reports/" + declaration["label"] + ".json", report)
    measurement = aggregate_pilot(registration, reports)
    writer.write_json("pilot_measurement.json", measurement)
    gates = record(
        "gate_evaluation",
        gates=[
            {
                "gate": "G0",
                "scope": "request/response and registered State identity",
                "passed": measurement["evidence_complete_count"] == 6,
            },
            {
                "gate": "G1",
                "scope": "two complete mock and two local failure controls",
                "passed": preparation["all_controls_passed"],
            },
            {
                "gate": "G2",
                "scope": "six fixed sessions, no replacement and bounded attempts",
                "passed": measurement["evidence_complete_count"] == 6
                and measurement["provider_attempts"] <= 72,
            },
            {
                "gate": "G3",
                "scope": "independent protocol validation and bounded interpretation",
                "passed": measurement["workflow_complete"],
            },
        ],
        all_model_sessions_successful_is_required=False,
        both_support_routes_are_required=False,
    )
    writer.write_json("gate_evaluation.json", gates)
    completed = all(gate["passed"] for gate in gates["gates"])
    report = record(
        "report",
        status="workflow_completed_as_scoped"
        if completed
        else "workflow_evidence_or_protocol_defect",
        gate_evaluation_id=gates["id"],
        stage=models.STAGE,
        preparation_report_id=preparation["id"],
        pilot_registration_id=registration["id"],
        model_configuration_id=config["id"],
        source_authority_id=authority["id"],
        measurement=measurement,
        no_model_success_threshold_for_workflow_completion=True,
        no_requirement_for_both_support_routes=True,
        original_protocol_and_source_bytes_unchanged=True,
        new_W_share=None,
        new_quotient_class_count=None,
        contribution_novelty_training_utility=None,
        old_W_share=1,
        old_finite_classes=2,
        older_compound_task_W=None,
        next_stage_authorized=False,
        old_mainline="remains_paused",
    )
    writer.write_json("report.json", report)
    writer.write_json(
        "decision.json",
        record(
            "decision",
            report_id=report["id"],
            status=report["status"],
            bounded_pilot_execution_finished=True,
            no_retry_replacement_or_extra_sampling=True,
            next_stage_authorized=False,
            old_mainline="remains_paused",
        ),
    )
    manifest = _manifest(writer, report)
    return {"report": report, "manifest": manifest}


def replay_pilot(*, repo_root: Path, replay_from: Path, output_directory: Path) -> dict[str, Any]:
    """Copy fixed execution bytes; independently rebuild reports without any callback."""
    root = repo_root.resolve()
    frozen = _frozen_inputs(root)
    saved = files_at(replay_from)
    old_manifest = json.loads(saved["artifact_manifest.json"])
    validate_manifest(saved, old_manifest["manifest_id"], old_manifest["artifact_root"])
    prep = read_json(replay_from, "preparation_report.json")
    config = read_json(replay_from, "model_config.json")
    protocol = read_json(replay_from, "protocol_contract.json")
    binding = read_json(replay_from, "model_adapter_binding.json")
    registration = read_json(replay_from, "pilot_registration.json")
    authority = read_json(replay_from, "source_authority.json")
    implementation = authority["implementation"]
    require(
        source_group(root, implementation["commit"], implementation["tree"], SOURCE_PATHS)
        == implementation,
        "pilot.replay_source",
    )
    require(
        config == model_config()
        and protocol == models.protocol_contract(frozen["parent_protocol"], config),
        "pilot.replay_configuration",
    )
    reports = [
        _audit(
            frozen,
            protocol,
            config,
            binding,
            declaration,
            replay_from / "online" / declaration["label"],
        )
        for declaration in registration["sessions"]
    ]
    for name in CONTROL_NAMES:
        declaration = read_json(replay_from, "control_declarations/" + name + ".json")
        mock_binding = read_json(replay_from, "control_bindings/" + name + ".json")
        audit = _audit(
            frozen, protocol, config, mock_binding, declaration, replay_from / "controls" / name
        )
        expected = read_json(replay_from, "control_results/" + name + ".json")
        require(audit == expected["independent_validation"], "pilot.replay_control_validation")
    regenerated = {
        "pilot_measurement.json",
        "gate_evaluation.json",
        "report.json",
        "decision.json",
        "artifact_manifest.json",
    }
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    for path, payload in sorted(saved.items()):
        if path not in regenerated and not path.startswith("online_reports/"):
            writer.write_bytes(path, payload)
    result = _finalize(writer, prep, config, registration, authority, reports)
    require(files_at(output_directory) == saved, "pilot.replay_byte_equality")
    _parent_unchanged(root, frozen)
    return {**result, "new_Provider_attempts": 0, "new_mock_callbacks": 0, "new_kernel_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("prepare", "online", "replay"), required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--source-tree")
    parser.add_argument("--credential-path", type=Path)
    parser.add_argument("--replay-from", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        require(
            args.external_audit is not None
            and args.source_commit is not None
            and args.source_tree is not None,
            "pilot.prepare_arguments",
        )
        result = prepare_pilot(
            repo_root=args.repo_root,
            external_audit=args.external_audit,
            source_commit=args.source_commit,
            source_tree=args.source_tree,
            output_directory=args.output_directory,
        )
    elif args.mode == "online":
        require(args.credential_path is not None, "pilot.online_credential_path")
        result = run_online(
            repo_root=args.repo_root,
            output_directory=args.output_directory,
            credential_path=args.credential_path,
        )
    else:
        require(args.replay_from is not None, "pilot.replay_input")
        result = replay_pilot(
            repo_root=args.repo_root,
            replay_from=args.replay_from,
            output_directory=args.output_directory,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
