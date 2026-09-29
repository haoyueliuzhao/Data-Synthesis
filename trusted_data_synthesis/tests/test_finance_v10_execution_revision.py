"""Exact funding-source transition controls; synthetic artifacts and no real wallet/HTTP."""

import copy
import json
from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research import probe_budget
from trusted_synthesis.finance_research import v10_execution_revision as revision
from trusted_synthesis.finance_research import v10_generation as generation
from trusted_synthesis.finance_research import v10_production as production
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.v6_collection import bound, persist, sha


def write_record(output, relative, body):
    path = output / relative
    value = bound(body)
    persist(path.parent, value, path.name)
    return value


def tamper_record(path, change):
    """Deliberately alter only a disposable fixture while retaining a valid self-digest."""
    value = json.loads(path.read_text())
    value.pop("id")
    change(value)
    value = bound(value)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return value


@pytest.fixture
def cohort(tmp_path, monkeypatch):
    output = tmp_path / "synthetic-cohort"
    output.mkdir()
    before = {
        "generation": {
            name: digest(["original", name])
            for name in generation.PROTECTED_GENERATION_SOURCES
        },
        "annotation": {
            name: digest(["original", name]) for name in production.phase_sources()
        },
    }
    after = copy.deepcopy(before)
    for scope, names in revision.ALLOWED_CHANGES.items():
        for name in names:
            after[scope][name] = digest(["authorized-funding-transition", name])
    live = copy.deepcopy(before)
    monkeypatch.setattr(generation, "source_binding", lambda: copy.deepcopy(live["generation"]))
    monkeypatch.setattr(production, "phase_sources", lambda: copy.deepcopy(live["annotation"]))
    monkeypatch.setattr(
        revision,
        "extra_sources",
        lambda: {name: digest(["synthetic-extra", name]) for name in revision.EXTRA_SOURCES},
    )
    config = {"run_id": "synthetic-no-wallet"}
    ledger = SimpleNamespace(
        run_id=config["run_id"],
        config=config,
        snapshot=lambda: {
            "v10_partition": {
                "batch_id": revision.BATCH_ID,
                "consumed": {
                    "review_mapping": dict.fromkeys(
                        ("requests", "dispatched", "spent", "held", "pending", "unknown"), 0
                    )
                },
            }
        },
    )
    slots = [
        {"slot_id": f"synthetic:{index}", "task_id": f"task-{index // 8}", "slot_index": index % 8}
        for index in range(8000)
    ]
    original_path = output / "original/record.json"
    write_record(output, original_path.relative_to(output), {"synthetic_original": True})
    policy = bound({"concurrency": 8, "model": "deepseek-flash"})
    plan = write_record(
        output,
        "registration/protocol.json",
        dict(
            batch_id=revision.BATCH_ID,
            concurrency=8,
            policy=policy,
            review_policy_id=policy["id"],
            slots=slots,
            budget_database=str(output / "must-not-open.sqlite3"),
            budget_config=config,
            budget_config_sha256=digest(config),
            protected_generation_sources=before["generation"],
            original_protocol={"path": str(original_path), "sha256": sha(original_path)},
        ),
    )
    runtime = production.register_runtime(output, plan, ledger)
    phase = write_record(
        output,
        "review_registration/record.json",
        dict(protocol_id=plan["id"], source_bindings=before["annotation"]),
    )
    generation_seal = write_record(
        output,
        "generation_seal/record.json",
        dict(protocol_id=plan["id"], denominator=8000, slots=[{"slot": s} for s in slots]),
    )
    write_record(
        output,
        "native_support/record.json",
        dict(
            protocol_id=plan["id"],
            generation_seal_id=generation_seal["id"],
            slot_denominator=8000,
            rows=[{"slot": s} for s in slots],
        ),
    )
    funding_receipt = write_record(
        output,
        revision.FUNDING_PATH,
        dict(
            run_id=config["run_id"],
            config_sha256=digest(config),
            batch_id=revision.BATCH_ID,
            authorization={"user_reply": revision.USER_REPLY},
            effective_hard_cap_microcny=2_000_000_000,
            effective_review_mapping_microcny=1_300_000_000,
            applied_after_requests=44444,
        ),
    )

    def financial_snapshot(path):
        assert path == plan["budget_database"]
        return {
            "snapshot": dict(
                pending_requests=0,
                unacknowledged_unknown_requests=0,
                halt=None,
                effective_hard_cap_microcny=2_000_000_000,
                funding_overlay=funding_receipt,
                requests_reserved=44444,
            )
        }

    monkeypatch.setattr(probe_budget, "read_budget_snapshot", financial_snapshot)
    original_bytes = {p: (output / p).read_bytes() for p in revision.HISTORICAL_PATHS}
    return SimpleNamespace(
        output=output,
        before=before,
        after=after,
        live=live,
        plan=plan,
        runtime=runtime,
        phase=phase,
        ledger=ledger,
        original_bytes=original_bytes,
    )


def entrypoints(cohort):
    return (
        lambda: generation.checked_plan(cohort.output),
        lambda: production.register_runtime(cohort.output, cohort.plan, cohort.ledger),
        lambda: production.register_review_phase(cohort.output, cohort.plan),
    )


def validate(cohort, scope="generation"):
    return revision.validate_source_transition(
        cohort.output,
        cohort.plan,
        scope=scope,
        original=cohort.before[scope],
        current=cohort.live[scope],
    )


def test_exact_transition_all_three_entrypoints_keep_original_records(cohort):
    cohort.live.update(copy.deepcopy(cohort.after))
    receipt = revision.register_execution_revision(cohort.output)
    assert receipt["original_sources"] == cohort.before
    assert receipt["effective_sources"] == cohort.after
    assert receipt["generation_already_complete"]
    for scope in revision.ALLOWED_CHANGES:
        assert validate(cohort, scope) == receipt
    assert [call() for call in entrypoints(cohort)] == [
        cohort.plan,
        cohort.runtime,
        cohort.phase,
    ]
    assert {p: (cohort.output / p).read_bytes() for p in cohort.original_bytes} == (
        cohort.original_bytes
    )
    before_retry = (cohort.output / revision.REVISION_PATH).read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        revision.register_execution_revision(cohort.output)
    assert (cohort.output / revision.REVISION_PATH).read_bytes() == before_retry


def test_unchanged_source_paths_need_no_new_revision(cohort, monkeypatch):
    def unexpected_transition(*args, **kwargs):
        pytest.fail("unchanged original source must not need a funding transition")

    monkeypatch.setattr(revision, "validate_source_transition", unexpected_transition)
    assert not (cohort.output / revision.REVISION_PATH).exists()
    assert [call() for call in entrypoints(cohort)] == [
        cohort.plan,
        cohort.runtime,
        cohort.phase,
    ]


@pytest.mark.parametrize("entrypoint", [0, 1, 2])
def test_changed_source_without_registration_is_rejected(cohort, entrypoint):
    cohort.live.update(copy.deepcopy(cohort.after))
    with pytest.raises(FileNotFoundError):
        entrypoints(cohort)[entrypoint]()


def test_even_allowed_budget_source_cannot_drift_after_registration(cohort):
    cohort.live.update(copy.deepcopy(cohort.after))
    revision.register_execution_revision(cohort.output)
    for scope in cohort.live:
        cohort.live[scope]["probe_budget.py"] = digest("unregistered-next-version")
    for call in entrypoints(cohort):
        with pytest.raises(ValueError, match="source transition missing or different"):
            call()


@pytest.mark.parametrize("name", ["v10_review_protocol.py", "v10_review_provider.py"])
def test_policy_or_provider_cannot_be_accepted_as_funding_change(cohort, name):
    cohort.live.update(copy.deepcopy(cohort.after))
    for scope in cohort.live:
        cohort.live[scope][name] = digest(["forbidden", name])
    with pytest.raises(ValueError, match="non-funding policy/provider/source change"):
        revision.register_execution_revision(cohort.output)
    assert not (cohort.output / revision.REVISION_PATH).exists()


@pytest.mark.parametrize("relative", revision.HISTORICAL_PATHS[:3])
def test_historical_registration_runtime_and_phase_cannot_be_replaced(cohort, relative):
    cohort.live.update(copy.deepcopy(cohort.after))
    revision.register_execution_revision(cohort.output)
    tamper_record(cohort.output / relative, lambda record: record.update(synthetic_tampering=True))
    with pytest.raises(ValueError, match="old registration was rewritten"):
        validate(cohort)


@pytest.mark.parametrize("case", ["generation_prefix", "native_prefix", "native_reordered"])
def test_registration_requires_all_8000_same_order_generation_and_native_slots(cohort, case):
    cohort.live.update(copy.deepcopy(cohort.after))
    if case == "generation_prefix":
        seal = tamper_record(
            cohort.output / "generation_seal/record.json",
            lambda record: record.update(slots=record["slots"][:-1], denominator=7999),
        )
        tamper_record(
            cohort.output / "native_support/record.json",
            lambda record: record.update(generation_seal_id=seal["id"]),
        )
    elif case == "native_prefix":
        tamper_record(
            cohort.output / "native_support/record.json",
            lambda record: record.update(rows=record["rows"][:-1], slot_denominator=7999),
        )
    else:
        tamper_record(
            cohort.output / "native_support/record.json",
            lambda record: record.update(rows=list(reversed(record["rows"]))),
        )
    with pytest.raises(ValueError, match="complete same-roster generation/native scoring"):
        revision.register_execution_revision(cohort.output)
    assert not (cohort.output / revision.REVISION_PATH).exists()
