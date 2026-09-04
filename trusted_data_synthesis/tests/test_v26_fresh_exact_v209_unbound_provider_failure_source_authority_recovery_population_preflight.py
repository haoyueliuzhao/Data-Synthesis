# ruff: noqa: E501
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight_models as models,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/8e03ba0c-a472-4ec1-b373-06fbc06e1fc0/pasted-text.txt"
)
REVIEW_SHA256 = "0b63d855ddd8e8707f3c0bdc2ddd4231b6a16fdaa986f7acb8e092f1491b58c2"
REVIEW_BYTE_COUNT = 10_739
DIRECTIVE = "参照审计继续实验"
DIRECTIVE_SHA256 = "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
DIRECTIVE_BYTE_COUNT = 24

V228_RUN_ID = (
    "finance_v26_228_fresh_exact_v209_subsequent_action_evidence_domain_closure_"
    "independent_audit_v1_20260904"
)
V228_MANIFEST_ID = (
    "finance_v26_228_artifact_manifest:"
    "7514b10d627fb19d3d42f1ad8f5e74e12bf0a152265d42742ab2b1b4e1391eaa"
)
V228_ARTIFACT_ROOT = (
    "finance_v26_228_artifact_root:92ed34f45846d1ba8e93cf5dd2e9d972f3f97bdbc69eb110135d8976e1d68aaf"
)
V228_MANIFEST_SHA256 = "42b3ded8192a175bc6a69636cc3a798073d0cc25a8785e540b903bbbc26501ae"
V228_DECISION_ID = (
    "finance_v26_228_independent_audit_decision:"
    "f6062949296f88a31e0de1af3ab59e5cfc933576750b7bcce709e5eb8594e540"
)
V228_TRANSITION_ID = (
    "finance_v26_228_transition:d84987584d8d07fd67554bf053e807305a987ac75285017722c207a66bd9d802"
)

V226_RUN_ID = (
    "finance_v26_226_fresh_exact_v209_parent_bound_postresponse_serializer_repair_"
    "exact_192_job_replacement_online_execution_v1_20260904"
)
V226_MANIFEST_ID = (
    "finance_v26_226_artifact_manifest:"
    "19cef807ae34c71c13d526c09c385163d1b30b2ced05322e3ec7e6f0e803d217"
)
V226_ARTIFACT_ROOT = (
    "finance_v26_226_artifact_root:7ac11713bf70dbd57297b6d87db0e6982ce5ad8222849e3a4826020904f95280"
)
V226_SUMMARY_ID = (
    "finance_v26_226_execution_summary:"
    "459c05325e7d8b1201b4ee9c5cca903876c8bd70f331b97db5d3245b59d82bbd"
)
V226_TRANSITION_ID = (
    "finance_v26_226_transition:e5b3a3b173cf91c5bf6150c3279fa053608c09d2f3d4679084d54cc4f32207b7"
)
V226_PROVIDER_SOURCE_SET_SHA256 = "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
V226_JOB_FAILURE_SHA256 = "bf06dd05d7431b80d5a218229dd0c1b6251b7e801ba4ade9e745d4a61ae3ca2f"
REASONING_ERROR_SHA256 = "4ef51bb293652969f948d4c8736bf7c4f469d44646576e455eaf238c97de7926"
JSON_ERROR_SHA256S = {
    62: "a5b3d29e992cbfb2617c3ef5207692fba727adfa83799f6e214591d53cb4ee51",
    139: "3c98c8f56a97682106aec03a9c7b21ecfd37304c2615d9774dc7bd70ea49914c",
}
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
UNBOUND_ORDINALS = (
    9,
    10,
    16,
    21,
    32,
    58,
    62,
    63,
    72,
    78,
    79,
    92,
    102,
    103,
    106,
    110,
    112,
    114,
    116,
    121,
    127,
    129,
    130,
    131,
    132,
    135,
    136,
    139,
    144,
    147,
    155,
    171,
    180,
)
FAILED_PHASES = {
    "first_action": (58, 116, 139),
    "subsequent_action": (
        9,
        10,
        21,
        32,
        63,
        72,
        79,
        92,
        103,
        106,
        110,
        112,
        114,
        121,
        127,
        129,
        130,
        131,
        132,
        135,
        144,
        147,
        155,
        171,
        180,
    ),
    "final": (16, 62, 78, 102, 136),
}


def _formal_dir() -> Path:
    direct = ROOT / subject.OUTPUT_DIR
    nested = ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR
    return direct if direct.is_dir() or not nested.is_dir() else nested


def _review_path() -> Path:
    explicit = os.environ.get("V26_229_EXTERNAL_REVIEW")
    formal = _formal_dir() / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.229 external review is unavailable")
    return path


def _load(root: Path, relative_path: str) -> dict[str, Any]:
    value = json.loads((root / relative_path).read_bytes())
    assert isinstance(value, dict)
    return value


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    formal = _formal_dir()
    if formal.is_dir() and (formal / "source_identity.json").is_file():
        source = _load(formal, "source_identity.json")
        source_identity = (str(source["source_commit"]), str(source["source_tree"]))
    else:
        commit = os.environ.get("V26_229_TEST_SOURCE_COMMIT")
        if commit is None:
            commit = subprocess.run(
                ("git", "rev-parse", "HEAD"),
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        tree = subprocess.run(
            ("git", "rev-parse", f"{commit}^{{tree}}"),
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        source_identity = (commit, tree)
    output = tmp_path_factory.mktemp("v26-229") / "formal"
    subject.build(
        repository_root=ROOT,
        output_dir=output,
        external_review=_review_path().read_bytes(),
        source_commit=source_identity[0],
        source_tree=source_identity[1],
    )
    return output


def test_exact_external_review_and_operator_directive_bytes(built: Path) -> None:
    authorization = models.ExternalAuthorization.model_validate(
        _load(built, "external_authorization.json")
    )
    review = (built / "external_review.txt").read_bytes()
    directive = (built / "operator_directive.txt").read_bytes()
    assert len(review) == REVIEW_BYTE_COUNT
    assert hashlib.sha256(review).hexdigest() == authorization.review_sha256 == REVIEW_SHA256
    assert authorization.review_byte_count == REVIEW_BYTE_COUNT
    assert directive == DIRECTIVE.encode("utf-8")
    assert len(directive) == DIRECTIVE_BYTE_COUNT
    assert hashlib.sha256(directive).hexdigest() == DIRECTIVE_SHA256
    assert authorization.operator_directive_sha256 == DIRECTIVE_SHA256
    assert authorization.consumed_stage == models.CONSUMED_STAGE
    assert authorization.provider_calls_authorized is False
    assert authorization.credential_lookups_authorized is False
    assert authorization.recovery_execution_authorized is False
    assert authorization.failed_job_reruns_authorized is False
    assert authorization.online_authorization_created is False


def test_exact_v228_freeze_preserves_predecessor_bytes_and_transition(built: Path) -> None:
    freeze = models.V228Freeze.model_validate(_load(built, "v228_freeze.json"))
    assert freeze.v228_run_id == V228_RUN_ID
    assert (freeze.saved_file_count, freeze.saved_byte_count) == (17, 45_679)
    assert (freeze.manifest_member_count, freeze.manifest_member_bytes) == (16, 42_978)
    assert freeze.v228_manifest_id == V228_MANIFEST_ID
    assert freeze.v228_artifact_root == V228_ARTIFACT_ROOT
    assert freeze.v228_decision_id == V228_DECISION_ID
    assert freeze.v228_transition_id == V228_TRANSITION_ID
    assert freeze.path_hash_byte_match_count == 17
    assert freeze.transition_names_consumed_stage == models.CONSUMED_STAGE
    assert freeze.transition_next_stage_authorized is False
    manifest_path = ROOT / models.V228_DIR / "artifact_manifest.json"
    assert len(manifest_path.read_bytes()) == 2_701
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == V228_MANIFEST_SHA256
    assert freeze.provider_calls == freeze.credential_lookups == 0
    assert freeze.passed


def test_v26_229_implementation_source_is_byte_bound(built: Path) -> None:
    source = models.SourceIdentity.model_validate(_load(built, "source_identity.json"))
    actual_tree = subprocess.run(
        ("git", "rev-parse", f"{source.source_commit}^{{tree}}"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert actual_tree == source.source_tree
    assert source.working_tree_bytes_match_source
    for relative_path, expected_sha, expected_bytes in (
        (source.model_relative_path, source.model_sha256, source.model_byte_count),
        (source.preflight_relative_path, source.preflight_sha256, source.preflight_byte_count),
    ):
        payload = (ROOT / relative_path).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected_sha
        assert len(payload) == expected_bytes
    assert source.provider_calls == source.credential_lookups == 0


def test_exact_v226_execution_freeze_remains_incomplete_and_immutable(built: Path) -> None:
    del built
    root = ROOT / models.V226_DIR
    files = _files(root)
    manifest = _load(root, "execution_artifact_manifest.json")
    summary = _load(root, "execution_summary.json")
    transition = _load(root, "prospective_transition.json")
    assert (len(files), sum(map(len, files.values()))) == (3_428, 99_765_014)
    assert len(manifest["members"]) == 3_427
    assert manifest["total_member_bytes"] == 99_047_004
    assert manifest["manifest_id"] == V226_MANIFEST_ID
    assert manifest["artifact_root"] == V226_ARTIFACT_ROOT
    assert summary["summary_id"] == V226_SUMMARY_ID
    assert transition["transition_id"] == V226_TRANSITION_ID
    assert summary["completed_job_record_count"] == 156
    assert summary["failure_record_count"] == 36
    assert summary["failure_partition"] == {"host_failure": 3, "unbound_provider_failure": 33}
    assert summary["execution_status"] == transition["execution_status"] == "incomplete"
    assert transition["replacement_or_recovery_authorized"] is False


def test_actual_v226_failure_records_select_the_exact_thirty_three_rows(built: Path) -> None:
    audit = models.V226SourceAuthorityAudit.model_validate(
        _load(built, "v226_source_authority_audit.json")
    )
    assert tuple(row.job_ordinal for row in audit.source_rows) == UNBOUND_ORDINALS
    assert audit.exact_source_count == 33
    assert audit.v226_actual_source_projection_sha256 == V226_PROVIDER_SOURCE_SET_SHA256
    assert audit.v228_exclusion_set_sha256 == V226_PROVIDER_SOURCE_SET_SHA256
    assert audit.v228_exclusion_set_match
    assert audit.excluded_host_failure_count == 3
    assert audit.source_and_exclusion_exact_set_equality
    assert all(row.failure_kind == "unbound_provider_failure" for row in audit.source_rows)
    assert all(row.job_error_sha256 == V226_JOB_FAILURE_SHA256 for row in audit.source_rows)
    assert len({row.historical_job_id for row in audit.source_rows}) == 33
    assert len({row.failure_record_id for row in audit.source_rows}) == 33
    assert len({row.failure_file_sha256 for row in audit.source_rows}) == 33
    assert audit.historical_v26_226_mutation_count == 0
    source_impl = inspect.getsource(subject._source_authority)
    assert "failure_kind" in source_impl
    assert "unbound_provider_failure" in source_impl


def test_provider_journal_is_closed_for_all_eighty_eight_calls(built: Path) -> None:
    source = models.V226SourceAuthorityAudit.model_validate(
        _load(built, "v226_source_authority_audit.json")
    )
    journal = models.ProviderJournalAuthority.model_validate(
        _load(built, "provider_journal_authority.json")
    )
    calls = tuple(call for row in source.source_rows for call in row.provider_calls)
    assert len(calls) == journal.provider_descriptor_count == 88
    assert sum(call.status == "succeeded" for call in calls) == 55
    assert sum(call.status == "provider_error" for call in calls) == 33
    assert journal.request_metadata_count == journal.usage_metadata_count == 88
    assert journal.response_metadata_count == 55
    assert journal.error_metadata_count == 33
    assert sum(len(call.artifact_bindings) for call in calls) == 264
    assert journal.reasoning_budget_error_count == 31
    assert journal.json_decode_error_count == 2
    assert journal.orphan_request_intent_count == journal.orphan_descriptor_count == 0
    assert journal.invalid_relation_count == 0
    assert journal.raw_request_count == journal.raw_provider_response_count == 0
    assert journal.private_reasoning_content_count == 0
    assert journal.relation_closed
    assert journal.source_row_ids == tuple(sorted(row.row_id for row in source.source_rows))
    for row in source.source_rows:
        assert row.successful_prefix_call_count == len(row.provider_calls) - 1
        assert row.failed_call_ordinal == len(row.provider_calls) - 1
        assert all(call.status == "succeeded" for call in row.provider_calls[:-1])
        failed = row.provider_calls[-1]
        assert failed.status == "provider_error"
        assert failed.response_sha256 is None
        assert failed.error_sha256 is not None
        assert row.failed_provider_call_id == failed.provider_call_id
        assert row.failed_descriptor_id == failed.descriptor_id
        assert row.failed_request_sha256 == failed.request_sha256


def test_offline_v209_replay_reconstructs_all_failed_requests_without_provider_calls(
    built: Path,
) -> None:
    source = models.V226SourceAuthorityAudit.model_validate(
        _load(built, "v226_source_authority_audit.json")
    )
    audit = models.RequestReplayAudit.model_validate(_load(built, "request_replay_audit.json"))
    source_by_ordinal = {row.job_ordinal: row for row in source.source_rows}
    assert tuple(row.job_ordinal for row in audit.rows) == UNBOUND_ORDINALS
    assert audit.exact_job_count == audit.exact_failed_request_match_count == 33
    assert sum(row.invocation_count for row in audit.rows) == 88
    assert sum(row.successful_prefix_call_count for row in audit.rows) == 55
    assert sum(row.exact_request_match_count for row in audit.rows) == 88
    assert sum(row.exact_response_match_count for row in audit.rows) == 55
    assert Counter(row.phases[-1] for row in audit.rows) == {
        "first_action": 3,
        "subsequent_action": 25,
        "final": 5,
    }
    assert {
        phase: tuple(row.job_ordinal for row in audit.rows if row.phases[-1] == phase)
        for phase in FAILED_PHASES
    } == FAILED_PHASES
    for row in audit.rows:
        parent = source_by_ordinal[row.job_ordinal]
        calls = parent.provider_calls
        failed = calls[-1]
        assert row.request_sha256s == tuple(call.request_sha256 for call in calls)
        assert row.response_sha256s == tuple(call.response_sha256 for call in calls[:-1])
        assert row.failed_request_sha256 == failed.request_sha256
        assert row.failed_request_byte_count == failed.request_byte_count
        assert row.failed_request_certificate_id == failed.certificate_id
        assert row.failed_pre_transport_receipt_id == failed.pre_transport_receipt_id
        assert row.failed_call_response_supplied_to_replay is False
        assert row.historical_provider_calls_reissued == row.provider_calls == 0
    assert audit.historical_provider_calls_reissued == audit.provider_calls == 0
    assert audit.credential_lookups == 0


def test_identifiability_partition_is_exact_empty_content_31_and_hash_only_2(
    built: Path,
) -> None:
    source = models.V226SourceAuthorityAudit.model_validate(
        _load(built, "v226_source_authority_audit.json")
    )
    audit = models.IdentifiabilityAudit.model_validate(_load(built, "identifiability_audit.json"))
    source_by_ordinal = {row.job_ordinal: row for row in source.source_rows}
    assert tuple(sorted(row.job_ordinal for row in audit.rows)) == UNBOUND_ORDINALS
    assert audit.exact_source_count == 33
    assert audit.identifiable_reasoning_budget_count == 31
    assert audit.unidentifiable_json_syntax_count == 2
    assert audit.exact_json_response_bytes_persisted_count == 0
    assert audit.exact_json_response_bytes_guessed_count == 0
    assert audit.recovery_request_authority_identifiable_count == 33
    reasoning = [row for row in audit.rows if row.error_type == "ReasoningBudgetExhaustedError"]
    assert len(reasoning) == 31
    assert all(row.failure_semantics_identifiable for row in reasoning)
    assert all(not row.exact_json_syntax_identifiable for row in reasoning)
    assert all(row.finish_reason == "length" for row in reasoning)
    assert all(row.public_content_length == 0 for row in reasoning)
    assert all(row.public_content_sha256 == EMPTY_SHA256 for row in reasoning)
    assert all(
        source_by_ordinal[row.job_ordinal].provider_calls[-1].error_sha256 == REASONING_ERROR_SHA256
        for row in reasoning
    )
    usage = []
    for row in reasoning:
        failed = source_by_ordinal[row.job_ordinal].provider_calls[-1]
        binding = next(
            item for item in failed.artifact_bindings if item.artifact_kind == "usage_metadata"
        )
        usage.append(_load(ROOT / models.V226_DIR, binding.relative_path)["telemetry"])
    assert Counter((item["completion_tokens"], item["reasoning_tokens"]) for item in usage) == {
        (16_384, 16_384): 28,
        (16_383, 16_383): 3,
    }


def test_two_json_failures_bind_only_persisted_hash_length_and_no_guessed_content(
    built: Path,
) -> None:
    source = models.V226SourceAuthorityAudit.model_validate(
        _load(built, "v226_source_authority_audit.json")
    )
    audit = models.IdentifiabilityAudit.model_validate(_load(built, "identifiability_audit.json"))
    source_by_ordinal = {row.job_ordinal: row for row in source.source_rows}
    rows = {row.job_ordinal: row for row in audit.rows if row.error_type == "JSONDecodeError"}
    assert set(rows) == {62, 139}
    assert source_by_ordinal[62].provider_calls[-1].error_sha256 == JSON_ERROR_SHA256S[62]
    assert source_by_ordinal[139].provider_calls[-1].error_sha256 == JSON_ERROR_SHA256S[139]
    assert (rows[62].finish_reason, rows[62].public_content_length) == ("length", 110)
    assert rows[62].public_content_sha256 == (
        "83b504accbc7117d749cecd9968235d48e5a44bb7366058950c85169fb916046"
    )
    assert (rows[139].finish_reason, rows[139].public_content_length) == ("stop", 3_200)
    assert rows[139].public_content_sha256 == (
        "f71276b285ebd1f80ce162d9c5bcb4460b65bef67bbdbb4b0c36c5ac1b42b718"
    )
    for row in rows.values():
        assert row.failure_semantics_identifiable is False
        assert row.exact_json_syntax_identifiable is False
        assert row.exact_json_response_bytes_persisted is False
        assert row.exact_json_response_bytes_guessed is False
        assert row.fresh_request_recovery_eligibility_identifiable


def test_recovery_population_has_fresh_ids_and_exact_source_parents(built: Path) -> None:
    source = models.V226SourceAuthorityAudit.model_validate(
        _load(built, "v226_source_authority_audit.json")
    )
    contract = models.RecoveryContract.model_validate(_load(built, "recovery_contract.json"))
    population = models.RecoveryPopulation.model_validate(_load(built, "recovery_population.json"))
    assert contract.exact_candidate_count == 33
    assert population.exact_job_count == population.fresh_recovery_job_identity_count == 33
    assert population.identifiable_reasoning_budget_count == 31
    assert population.unidentifiable_json_syntax_count == 2
    assert population.historical_job_identity_overlap_count == 0
    recovery_ids = tuple(row.recovery_job_id for row in population.jobs)
    assert recovery_ids == tuple(sorted(set(recovery_ids)))
    historical_ids = {
        value
        for row in source.source_rows
        for value in (
            row.historical_job_id,
            row.failure_record_id,
            *(call.provider_call_id for call in row.provider_calls),
            *(call.descriptor_id for call in row.provider_calls),
        )
    }
    assert not set(recovery_ids) & historical_ids
    source_by_id = {row.row_id: row for row in source.source_rows}
    candidate_ids = []
    for job in population.jobs:
        candidate = job.candidate
        candidate_ids.append(candidate.candidate_id)
        parent = source_by_id[candidate.source_row_id]
        assert candidate.historical_job_id == parent.historical_job_id
        assert candidate.failure_record_id == parent.failure_record_id
        assert candidate.failed_provider_call_id == parent.failed_provider_call_id
        assert candidate.failed_descriptor_id == parent.failed_descriptor_id
        assert candidate.exact_failed_request_sha256 == parent.failed_request_sha256
        assert candidate.historical_job_identity_retained_only_as_parent
        assert candidate.historical_response_content_guessed is False
        assert candidate.historical_json_syntax_detail_available is False
        assert candidate.historical_job_reclassified is False
        assert candidate.replacement_or_recovery_attempted is False
        assert candidate.provider_calls_authorized is False
        assert candidate.online_execution_authorized is False
        assert job.historical_job_identity_retained_only_as_parent
        assert job.historical_job_reclassified is False
        assert job.successful_prefix_provider_calls_authorized == 0
        assert job.failed_request_reissue_authorized == 0
        assert job.replacement_response_authorization_count == 0
        assert job.recovery_execution_authorized is False
        assert job.provider_calls_authorized is False
        saved = models.RecoveryCandidate.model_validate(
            _load(built, f"recovery_candidates/job_{candidate.job_ordinal:03d}.json")
        )
        assert saved == candidate
    assert contract.candidate_ids == tuple(sorted(candidate_ids))
    assert population.provider_calls_authorized is False
    assert population.recovery_execution_authorized is False
    assert population.online_authorization_created is False


def test_direct_attacks_reject_before_candidate_or_recovery_job_write(built: Path) -> None:
    audit = models.NegativeControlAudit.model_validate(_load(built, "negative_control_audit.json"))
    assert tuple(row.attack_name for row in audit.results) == models.NEGATIVE_CONTROL_NAMES
    assert audit.attack_count == audit.rejection_count == len(models.NEGATIVE_CONTROL_NAMES)
    assert audit.accepted_count == 0
    assert audit.provider_calls == 0
    assert all(row.rejected for row in audit.results)
    assert all(row.rejection_stage and len(row.reason_sha256) == 64 for row in audit.results)
    assert all(row.candidate_writes_before_rejection == 0 for row in audit.results)
    assert all(row.recovery_job_writes_before_rejection == 0 for row in audit.results)
    assert all(row.provider_calls_before_rejection == 0 for row in audit.results)
    by_name = {row.attack_name: row for row in audit.results}
    assert "invent_json_response_bytes" in by_name
    assert "historical_job_identity_reused" in by_name
    assert "authorize_provider_call" in by_name
    assert "authorize_online_execution" in by_name


def test_static_and_materialized_scope_boundary_is_zero(built: Path) -> None:
    scope = models.ScopeBoundaryAudit.model_validate(_load(built, "scope_boundary_audit.json"))
    assert all(
        value == 0
        for value in (
            scope.provider_calls,
            scope.credential_lookups,
            scope.model_client_constructions,
            scope.recovery_executions,
            scope.failed_job_reruns,
            scope.historical_v26_226_writes,
            scope.historical_outcome_backfills,
            scope.empirical_rows,
            scope.online_authorizations,
            scope.qa_reads,
            scope.mapper_rows,
            scope.state_rows,
            scope.frequency_rows,
            scope.contribution_rows,
            scope.vtdo_rows,
            scope.training_runs,
            scope.releases,
            scope.production_writes,
        )
    )
    assert scope.passed
    source_path = Path(inspect.getsourcefile(subject) or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any("deepseek" in name.lower() for name in imported)
    source_text = inspect.getsource(subject)
    assert "DEEPSEEK_API_KEY" not in source_text
    assert "load_dotenv" not in source_text


def test_gate_decision_and_transition_remain_noncompensatory_and_offline(built: Path) -> None:
    gate = models.GateEvaluation.model_validate(_load(built, "gate_evaluation.json"))
    decision = models.Decision.model_validate(_load(built, "decision.json"))
    transition = models.Transition.model_validate(_load(built, "transition.json"))
    report = models.Report.model_validate(_load(built, "report.json"))
    assert tuple(row.name for row in gate.gates) == models.GATE_NAMES
    assert gate.passed_count == len(models.GATE_NAMES)
    assert gate.failed_count == 0
    assert gate.noncompensatory
    assert all(row.passed and row.evidence_ids for row in gate.gates)
    assert decision.decision == report.decision == models.DECISION_VALUE
    assert decision.exact_source_count == decision.fresh_recovery_job_count == 33
    assert decision.provider_calls == decision.empirical_rows == 0
    assert decision.recovery_execution_authorized is False
    assert decision.online_execution_authorized is False
    assert report.exact_source_count == report.fresh_recovery_job_count == 33
    assert report.identifiable_reasoning_budget_count == 31
    assert report.unidentifiable_json_syntax_count == 2
    assert report.provider_calls == report.credential_lookups == 0
    assert report.recovery_executions == report.failed_job_reruns == 0
    assert report.historical_v26_226_mutations == report.empirical_rows == 0
    assert report.online_authorizations == 0
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.next_stage_authorized is False
    assert transition.independent_audit_required
    assert transition.recovery_population_preflight_only
    assert transition.recovery_execution_authorized is False
    assert transition.provider_calls_authorized is False
    assert transition.credential_lookups_authorized is False
    assert transition.failed_job_reruns_authorized is False
    assert transition.online_authorization_created is False
    assert transition.historical_v26_226_mutation_authorized is False
    assert transition.empirical_estimation_authorized is False


def test_models_reject_guessed_json_and_historical_identity_reuse(built: Path) -> None:
    identifiability = _load(built, "identifiability_audit.json")
    json_index = next(
        index for index, row in enumerate(identifiability["rows"]) if row["job_ordinal"] == 62
    )
    forged = json.loads(json.dumps(identifiability))
    forged["rows"][json_index]["reconstructed_json"] = '{"guessed":true}'
    with pytest.raises(ValueError):
        models.IdentifiabilityAudit.model_validate(forged)

    population = _load(built, "recovery_population.json")
    forged_population = json.loads(json.dumps(population))
    forged_population["jobs"][0]["recovery_job_id"] = forged_population["jobs"][0]["candidate"][
        "historical_job_id"
    ]
    with pytest.raises(ValueError):
        models.RecoveryPopulation.model_validate(forged_population)


def test_manifest_and_second_build_are_byte_identical(built: Path, tmp_path: Path) -> None:
    manifest = models.ArtifactManifest.model_validate(_load(built, "artifact_manifest.json"))
    actual = _files(built)
    assert manifest.self_excluding
    assert manifest.manifest_relative_path not in {
        member.relative_path for member in manifest.members
    }
    assert manifest.file_count == len(actual) - 1
    assert manifest.total_member_bytes == sum(
        len(payload)
        for relative_path, payload in actual.items()
        if relative_path != manifest.manifest_relative_path
    )
    for member in manifest.members:
        payload = actual[member.relative_path]
        assert member.sha256 == hashlib.sha256(payload).hexdigest()
        assert member.byte_count == len(payload)

    predecessor_root = ROOT / models.V226_DIR
    before = {
        name: (predecessor_root / name).read_bytes()
        for name in (
            "execution_artifact_manifest.json",
            "execution_summary.json",
            "prospective_transition.json",
        )
    }
    source = _load(built, "source_identity.json")
    rebuilt = tmp_path / "empty" / "rebuilt"
    subject.build(
        repository_root=ROOT,
        output_dir=rebuilt,
        external_review=_review_path().read_bytes(),
        source_commit=str(source["source_commit"]),
        source_tree=str(source["source_tree"]),
    )
    assert _files(rebuilt) == actual
    assert before == {name: (predecessor_root / name).read_bytes() for name in before}
