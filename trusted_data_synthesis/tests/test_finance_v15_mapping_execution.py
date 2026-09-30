"""Finite V15 temporary-wallet/memory tests, never real mapping/prefix/model work."""

import asyncio
import copy
import hashlib
from types import SimpleNamespace

import pytest
from test_finance_research_probe_provider import Client
from test_finance_unknown_abandonment import table
from test_finance_v10_budget import stopped_history, synthetic_parent  # noqa: F401
from test_finance_v12_budget_provider import clone, funded, registered  # noqa: F401
from test_finance_v13_material_execution import v13_seed  # noqa: F401
from test_finance_v13_material_protocol import bindings
from test_finance_v14_material_execution import reply, residual_seed, save  # noqa: F401

from trusted_synthesis.finance_research import v14_budget as parent_budget
from trusted_synthesis.finance_research import v15_budget as budget
from trusted_synthesis.finance_research import v15_mapping_controller as ctl
from trusted_synthesis.finance_research.contracts import digest, invocation_identity
from trusted_synthesis.finance_research.probe_budget import BudgetUnavailable, DuplicateInvocation
from trusted_synthesis.finance_research.providers import _json

PROTOCOL = "CPU-v15-pre-prefix-mapping"
KEY = "CPU-fixture-not-an-actual-key"


@pytest.fixture(scope="module")
def mapping_seed(tmp_path_factory, residual_seed):  # noqa: F811
    from trusted_synthesis.finance_research import v15_mapping_protocol as protocol

    path, parent_plan, requests, _ = residual_seed
    folder = tmp_path_factory.mktemp("v15-synthetic-seed")
    ledger = clone(path, folder / "wallet.sqlite")
    parent_budget.register_matrix(
        ledger,
        parent_plan,
        parent_budget.authorization_definition(parent_plan),
        backup_path=folder / "before-v14.sqlite",
    )
    groups = parent_plan["fixed_task_slots"]
    tasks = list(groups)
    fixed = tasks[:54]
    inherited = tasks[54:]
    source = folder / "source-V14"
    seal = budget.bound(dict(schema="CPU-only-V14-completion", expected_calls=309))
    save(source / "completion_seal/record.json", seal)
    mp = pytest.MonkeyPatch()
    mp.setattr(budget, "SOURCE_SEAL_ID", seal["id"])
    population = budget.bound(
        dict(candidate_slot_ids=[s for ss in groups.values() for s in ss], fixed_task_slots=groups)
    )
    parent_ref = save(source / "definition/record.json", population)
    support = budget.bound(
        dict(
            N=744, training_task_ids=tasks, task_support={t: {"CPU_only": True} for t in inherited}
        )
    )
    support_ref = save(source / "material/support/record.json", support)
    review = budget.bound(
        dict(
            schema="v15_mapping_review.v1",
            fixed_task_ids=fixed,
            old_690_partition_evidence_chi_unchanged=True,
            inherited_mapping_authority_refs=[dict(task_id=t) for t in inherited],
            derived_mapping_authority_refs=[dict(task_id=t) for t in fixed[1:]],
            residual_mapping_task_ids=fixed[:1],
        )
    )
    review_ref = save(folder / "mapping_review/summary/record.json", review)
    definition = budget.bound(
        dict(source_v14_definition=parent_ref, source_material_support=support_ref)
    )
    definition_ref = save(folder / "definition/record.json", definition)
    views = requests[1]["views"]
    req = protocol.prepare_mapping(views, protocol_id=PROTOCOL, source_bindings=bindings(views))
    assert req["task_id"] == fixed[0]
    body = protocol.request_body(req)
    job = dict(
        kind="mapping",
        purpose="mapping",
        role="mapping",
        task_id=req["task_id"],
        slot_id=None,
        slot_ids=req["slot_ids"],
        episode_id=req["episode_id"],
        authority_reason="mapping_completion",
        max_output_tokens=req["max_output_tokens"],
        request_sha256=digest(body),
        request_body_sha256=hashlib.sha256(_json(body).encode()).hexdigest(),
    )
    plan = budget.bound(
        dict(
            batch_id=budget.BATCH_ID,
            source_batch_id=budget.SOURCE_BATCH_ID,
            source_root=str(source),
            source_protocol_id=parent_plan["id"],
            source_review_seal_id=seal["id"],
            definition=definition_ref,
            mapping_review=review_ref,
            fixed_task_slots=groups,
            fixed_unresolved_task_ids=fixed,
            residual_task_ids=fixed[:1],
            model="deepseek-flash",
            protocol_identity=PROTOCOL,
            jobs=[job],
            expected_requests=1,
            purpose_counts={"mapping": 1},
            concurrency={"max": 16, "ramp": [{"settled_at_least": 0, "workers": 16}]},
        )
    )
    yield ledger.path, plan, req, review, definition
    mp.undo()


@pytest.fixture
def matrix(tmp_path, mapping_seed):
    path, plan, req, _, _ = mapping_seed
    ledger = clone(path, tmp_path / "wallet.sqlite")
    permit = budget.register_matrix(
        ledger,
        plan,
        budget.authorization_definition(plan),
        backup_path=tmp_path / "before-v15.sqlite",
    )
    return ledger, plan, req, permit


def test_new_mapping_scope_preserves_parent_money_unknowns_and_rows(matrix):
    ledger, plan, _, permit = matrix
    assert permit["job_count"] == 1 and permit["purpose_counts"] == {"mapping": 1}
    assert (
        permit["parent_v14_permit_id"]
        and not permit["authorization"]["training_authorized_by_this_permit"]
    )
    for name in ("requests", "counters", "v10_quotas"):
        assert table(ledger.path, name) == table(permit["backup"]["path"], name)
    assert (
        budget.register_matrix(
            ledger,
            plan,
            budget.authorization_definition(plan),
            backup_path=permit["backup"]["path"],
        )
        == permit
    )


def test_previously_resolved_task_or_second_attempt_cannot_borrow_new_permit(matrix):
    from trusted_synthesis.finance_research import v15_mapping_protocol as protocol

    ledger, plan, request, _ = matrix
    body = protocol.request_body(request)
    resolved = next(
        t for t in plan["fixed_task_slots"] if t not in plan["fixed_unresolved_task_ids"]
    )
    for eid, attempt in (
        (budget.mapping_episode_id(PROTOCOL, resolved), 1),
        (request["episode_id"], 2),
        ("v15projection:" + "0" * 64, 1),
    ):
        coords = invocation_identity(
            dict(run_id=ledger.run_id, episode_id=eid, attempt_index=attempt), turn_index=0
        )
        with pytest.raises(BudgetUnavailable):
            ledger.reserve(
                coords["invocation_id"],
                coordinates=coords,
                request=body,
                request_body=_json(body).encode(),
            )


def test_provider_real_factory_temp_ledger_original_failed_response_and_zero_replay(matrix):
    from trusted_synthesis.finance_research import v15_mapping_provider as provider

    ledger, _, request, _ = matrix
    client = Client(reply())
    artifact = asyncio.run(
        provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
    )
    row = ledger.request_record(artifact["budget_invocation_id"])
    record = provider.paid_record(request, artifact, row)
    assert (
        record["schema"] == "v15_paid_material_annotation.v1"
        and not record["inspection"]["mapping_admitted"]
    )
    assert not record["inspection"]["production_admitted"]
    assert provider.restore_settled(row, request) == artifact
    with pytest.raises(DuplicateInvocation):
        asyncio.run(
            provider.request_once(ledger=ledger, api_key=KEY, request=request, client=client)
        )
    assert len(client.calls) == 1


def test_unsupported_offline_credit_cannot_shrink_fixed54(tmp_path, mapping_seed):
    path, plan, _, review, definition = mapping_seed
    ledger = clone(path, tmp_path / "wallet.sqlite")
    bad = copy.deepcopy(review)
    bad["derived_mapping_authority_refs"].pop()
    bad = budget.bound({k: v for k, v in bad.items() if k != "id"})
    altered = copy.deepcopy(plan)
    altered["mapping_review"] = save(tmp_path / "bad-review/record.json", bad)
    altered = budget.bound({k: v for k, v in altered.items() if k != "id"})
    with pytest.raises(ValueError, match="residual"):
        budget.register_matrix(
            ledger,
            altered,
            budget.authorization_definition(altered),
            backup_path=tmp_path / "absent.sqlite",
        )
    assert not (tmp_path / "absent.sqlite").exists()


def test_zero_residual_seals_without_wallet_key_client_or_student(tmp_path, monkeypatch):
    from trusted_synthesis.finance_research import v15_mapping_registration as registration

    plan = dict(
        id="CPU-no-new-calls",
        protocol_identity=PROTOCOL,
        expected_requests=0,
        purpose_counts={"mapping": 0},
        mapping_review={},
        source_review_seal_id="source",
        fixed_unresolved_task_ids=[f"t{i}" for i in range(54)],
    )
    ctx = SimpleNamespace(output=tmp_path, jobs=[], plan=plan)
    monkeypatch.setattr(ctl, "Context", lambda output: ctx)

    def forbidden(*args, **kwargs):
        raise AssertionError("zero-call path must not open wallet/read key/start HTTP")

    monkeypatch.setattr(registration, "ledger_for", forbidden)
    monkeypatch.setattr(ctl, "_key", forbidden)
    monkeypatch.setattr(ctl, "_provider", forbidden)
    seal = asyncio.run(ctl.run_material(tmp_path))
    assert (
        seal["expected_calls"] == seal["actual_returns"] == 0
        and seal["mapping_complete_calls"] == 0
    )
    assert not seal["production_admitted"] and (tmp_path / "completion_seal/record.json").is_file()


def test_new_request_contains_only_original_public_input_not_student_state(mapping_seed):
    from trusted_synthesis.finance_research import v15_mapping_protocol as protocol

    _, _, request, _, _ = mapping_seed
    body = protocol.request_body(request)
    assert body["model"] == "deepseek-flash" and body["thinking"] == {"type": "disabled"}
    assert request["purpose"] == request["role"] == "mapping"
    # The only request inputs came from the existing original views/host-only refs;
    # no prefix path, loss, gradient, checkpoint or evaluation fixture was opened.
    assert "NOT_FOR_MODEL" not in _json(body)
    assert all(m["role"] in {"system", "user"} for m in body["messages"])
