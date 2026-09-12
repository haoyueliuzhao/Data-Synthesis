"""Independent catalog/budget controls: synthetic files, no source production or API."""

import hashlib
import io
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import (
    acquisition,
    budget,
    catalog,
    panels,
    protocol,
)
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.budget import (
    INPUT_RESERVATION,
    OUTPUT_CAP,
    BudgetRejected,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record

RESERVED = INPUT_RESERVATION + OUTPUT_CAP
OLD_DEBIT = {"id": "inherited_surface_rewrite", "tokens": 211338}
OLD_TASKS = ["old_task_" + str(index) for index in range(233)]


def put_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return raw


def make_parent(root, relative="parent", *, families=("annual_flow",), task_ids=None):
    directory = root / relative
    members, tasks = [], []
    task_ids = task_ids or ["task_" + str(index) for index in range(len(families))]

    def member(path, value):
        raw = put_json(directory / path, value)
        members.append({"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        return raw

    for task_id, family in zip(task_ids, families, strict=True):
        public_path = f"tasks/{task_id}/teacher_visible.json"
        public = member(public_path, [{"role": "user", "content": "PUBLIC_ONLY:" + task_id}])
        bundle = record(
            "TaskBundle",
            task_id=task_id,
            family=family,
            source_cluster="cik:0000000001",
            surface_realization={
                "surface_version_id": "surface:" + task_id,
                "public_messages_sha256": hashlib.sha256(public).hexdigest(),
                "category": "canonical_fallback",
            },
            private={
                "canonical_target": {"quantity": "difference"},
                "PRIVATE_CANARY_NEVER_OPEN_ONLINE": "secret-answer-not-public",
            },
        )
        path = f"tasks/{task_id}/task_bundle.json"
        member(path, bundle)
        tasks.append({"task_id": task_id, "bundle_id": bundle["id"], "path": path})
    member("native_bindings.json", {"PRIVATE_BINDINGS_CANARY": "offline-only"})
    member("catalog.json", record("fixed_task_catalog", tasks=tasks))
    manifest = record("manifest", members=members)
    put_json(directory / "manifest.json", manifest)
    return catalog.Parent(root, relative, manifest["id"])


def composed(root, *, families=("annual_flow",)):
    parent = make_parent(root, families=families)
    full, public = catalog.compose(root, root / "composed", [parent], "synthetic_freeze")
    return parent, full, public


def ledger(path, *, cap=budget.GLOBAL_CAP, prior=None, request_cap=54, token_cap=525312):
    return budget.IncrementLedger(
        path,
        "synthetic_bridge",
        prior_debits=[OLD_DEBIT] if prior is None else prior,
        global_cap=cap,
        request_cap=request_cap,
        token_cap=token_cap,
    )


def settle(value, request, *, usage=None, success=True, outcome="response_received"):
    value.mark_sent(request["request_id"])
    return value.settle(
        request["request_id"],
        usage=usage,
        http_success=success,
        response_model="synthetic-model-no-request",
        outcome=outcome,
    )


def test_parent_requires_original_content_addressed_manifest_and_explicit_pin(tmp_path):
    parent = make_parent(tmp_path)
    assert parent.verify_all() == parent.manifest["id"]
    with pytest.raises(ValueError, match="manifest_pin"):
        catalog.Parent(tmp_path, "parent", "manifest:wrong")
    altered = dict(parent.manifest)
    altered["unhashed_mutation"] = True
    put_json(tmp_path / "parent" / "manifest.json", altered)
    with pytest.raises(ValueError, match="content_addressed"):
        catalog.Parent(tmp_path, "parent", parent.manifest["id"])


def test_real_frozen_parent_has_exact_233_scientific_tasks():
    root = Path(__file__).resolve().parents[2]
    if not (root / protocol.PARENT / "manifest.json").exists():
        pytest.skip("optional historical parent artifacts are not installed")
    parent = catalog.Parent(root, protocol.PARENT, protocol.PARENT_MANIFEST)
    entries = parent.read("catalog.json")["tasks"]
    assert len(entries) == len({row["task_id"] for row in entries}) == 233
    assert parent.descriptor()["manifest_id"] == protocol.PARENT_MANIFEST


def test_parent_duplicate_members_and_undeclared_paths_rejected(tmp_path):
    parent = make_parent(tmp_path)
    with pytest.raises(ValueError, match="member_declared"):
        parent.bytes("not_in_manifest.json")
    duplicate = record("manifest", members=parent.manifest["members"] * 2)
    put_json(tmp_path / "parent" / "manifest.json", duplicate)
    with pytest.raises(ValueError, match="unique_parent_members"):
        catalog.Parent(tmp_path, "parent", duplicate["id"])


def test_parent_rejects_changed_member_bytes(tmp_path):
    parent = make_parent(tmp_path)
    path = tmp_path / "parent" / "native_bindings.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="parent_member_bytes"):
        parent.read("native_bindings.json")


@pytest.mark.parametrize("action", ["descriptor", "verify_all", "read"])
def test_parent_cannot_mix_old_manifest_ID_with_replaced_manifest_bytes(tmp_path, action):
    parent = make_parent(tmp_path)
    changed = record("manifest", members=parent.manifest["members"], replaced_manifest=True)
    put_json(tmp_path / "parent" / "manifest.json", changed)
    with pytest.raises(ValueError):
        if action == "read":
            parent.read("catalog.json")
        else:
            getattr(parent, action)()


@pytest.mark.parametrize("target", ["member", "manifest", "directory"])
def test_parent_does_not_accept_internal_symlink_as_original_regular_file(tmp_path, target):
    parent = make_parent(tmp_path)
    directory = tmp_path / "parent"
    if target == "directory":
        (tmp_path / "alias").symlink_to(directory, target_is_directory=True)
        with pytest.raises(ValueError):
            catalog.Parent(tmp_path, "alias", parent.manifest["id"])
        return
    name = "manifest.json" if target == "manifest" else "native_bindings.json"
    original = directory / name
    moved = directory / (name + ".original")
    original.rename(moved)
    original.symlink_to(moved)
    with pytest.raises(ValueError):
        if target == "manifest":
            catalog.Parent(tmp_path, "parent", parent.manifest["id"])
        else:
            parent.read(name)


def test_public_catalog_only_opens_public_index_and_public_file(tmp_path, monkeypatch):
    parent, full, public = composed(tmp_path)
    opened = []
    original_read = Path.read_bytes

    def audited_read(path):
        opened.append(str(path))
        assert path.name not in {"task_bundle.json", "native_bindings.json", "manifest.json"}
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", audited_read)
    online = catalog.PublicCatalog(tmp_path, "composed/public_catalog.json", public["id"])
    result = online.public_envelope("task_0")
    assert len(opened) == 2
    assert {Path(path).name for path in opened} == {"public_catalog.json", "teacher_visible.json"}
    assert "PRIVATE" not in json.dumps(result)
    assert result["messages"] == [{"role": "user", "content": "PUBLIC_ONLY:task_0"}]
    assert set(result["identity"]) == set(catalog.IDENTITY_FIELDS)


def test_public_index_pin_whitelist_and_duplicate_task_identity(tmp_path):
    _, _, public = composed(tmp_path)
    with pytest.raises(ValueError, match="public_index_pin"):
        catalog.PublicCatalog(tmp_path, "composed/public_catalog.json", "wrong")
    for tasks in (public["tasks"] * 2, [{**public["tasks"][0], "bundle_path": "private.json"}]):
        changed = record(
            "public_task_catalog",
            source_catalog_id=public["source_catalog_id"],
            tasks=tasks,
            contains_private_bundles=False,
        )
        put_json(tmp_path / "composed" / "public_catalog.json", changed)
        with pytest.raises(ValueError):
            catalog.PublicCatalog(tmp_path, "composed/public_catalog.json", changed["id"])


@pytest.mark.parametrize("change", ["bytes", "internal_symlink", "outside_source"])
def test_public_source_byte_identity_and_path_safety(tmp_path, change):
    _, _, public = composed(tmp_path)
    online = catalog.PublicCatalog(tmp_path, "composed/public_catalog.json", public["id"])
    path = tmp_path / public["tasks"][0]["public_path"]
    if change == "bytes":
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "internal_symlink":
        moved = path.with_suffix(".original")
        path.rename(moved)
        path.symlink_to(moved)
    else:
        online.tasks["task_0"]["public_path"] = "../outside.json"
    with pytest.raises(ValueError):
        online.public_envelope("task_0")


def test_public_index_cannot_be_opened_outside_workspace_root(tmp_path):
    _, _, public = composed(tmp_path)
    inner = tmp_path / "inner_root"
    inner.mkdir()
    with pytest.raises(ValueError):
        catalog.PublicCatalog(inner, "../composed/public_catalog.json", public["id"])


@pytest.mark.parametrize("family,scale", list(catalog.FAMILY_TO_SCALE.items()))
def test_composition_uses_explicit_family_mapping(tmp_path, family, scale):
    _, full, public = composed(tmp_path, families=(family,))
    assert full["tasks"][0]["family"] == family
    assert full["tasks"][0]["scale_group"] == scale
    assert "scale_group" not in public["tasks"][0]
    assert full["preserved_parent_builds"] and full["shared_AB_public_bytes"]


def test_unknown_family_and_duplicate_scientific_task_rejected(tmp_path):
    unknown = make_parent(tmp_path, "unknown", families=("different_metric_not_registered",))
    with pytest.raises(ValueError, match="explicit_family_mapping"):
        catalog.compose(tmp_path, tmp_path / "bad_family", [unknown], "freeze")
    old = make_parent(tmp_path, "old")
    new = make_parent(tmp_path, "new")
    with pytest.raises(ValueError, match="duplicate_scientific_task"):
        catalog.compose(tmp_path, tmp_path / "bad_duplicate", [old, new], "freeze")


@pytest.mark.parametrize("duplicated_field", ["tasks", "parents"])
def test_offline_catalog_rejects_duplicate_authorities(tmp_path, duplicated_field):
    _, full, _ = composed(tmp_path)
    fields = {key: value for key, value in full.items() if key not in {"schema_version", "id"}}
    fields[duplicated_field] *= 2
    changed = record("composed_task_catalog", **fields)
    put_json(tmp_path / "composed" / "catalog.json", changed)
    with pytest.raises(ValueError):
        catalog.OfflineCatalog(tmp_path, "composed/catalog.json", changed["id"])


def test_offline_fixture_cannot_mix_a_different_public_surface_catalog(tmp_path):
    _, full, public = composed(tmp_path)
    fields = {key: value for key, value in public.items() if key not in {"schema_version", "id"}}
    fields["tasks"][0]["surface_version_id"] = "unrelated-surface"
    changed = record("public_task_catalog", **fields)
    put_json(tmp_path / "composed" / "other_public.json", changed)
    offline = catalog.OfflineCatalog(tmp_path, "composed/catalog.json", full["id"])
    online = catalog.PublicCatalog(tmp_path, "composed/other_public.json", changed["id"])
    with pytest.raises(ValueError):
        offline.fixture("task_0", online)


def test_historical_debit_is_carried_into_shared_global_allowance(tmp_path):
    value = ledger(tmp_path / "ledger.sqlite3")
    value.register(["new_task"], OLD_TASKS)
    reservation = value.reserve("new_task")
    snapshot = value.snapshot()
    assert snapshot["previous_registered_debit"] == 211338
    assert snapshot["cumulative_conservative_debit"] == 211338 + RESERVED
    assert snapshot["remaining_registered_global_allowance"] == 1000000000 - 211338 - RESERVED
    assert reservation["reserved_tokens"] == 9728
    assert snapshot["Teacher_requests_allowed_in_this_stage"] == 0


def test_global_exhaustion_is_atomic_and_reopen_does_not_reset_prior_debit(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    cap = 211338 + RESERVED
    value = ledger(path, cap=cap)
    value.register(["new_1", "new_2"], OLD_TASKS)
    value.reserve("new_1")
    reopened = ledger(path, cap=cap)
    with pytest.raises(BudgetRejected, match="cumulative_budget_exhausted"):
        reopened.reserve("new_2")
    snapshot = reopened.snapshot()
    assert snapshot["request_reservations"] == 1
    assert snapshot["remaining_registered_global_allowance"] == 0
    with pytest.raises(BudgetRejected, match="cumulative_policy_identity"):
        ledger(path, cap=cap + RESERVED)


def test_parallel_requests_cannot_exceed_cumulative_token_cap(tmp_path):
    value = ledger(tmp_path / "ledger.sqlite3", cap=211338 + 7 * RESERVED)
    tasks = ["new_" + str(index) for index in range(27)]
    value.register(tasks, OLD_TASKS)

    def reserve(task_id):
        try:
            return value.reserve(task_id)
        except BudgetRejected:
            return None

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(reserve, tasks))
    assert sum(result is not None for result in results) == 7
    snapshot = value.snapshot()
    assert snapshot["request_reservations"] == 7
    assert snapshot["remaining_registered_global_allowance"] == 0


def test_parallel_repeated_initial_request_uses_one_reservation(tmp_path):
    value = ledger(tmp_path / "ledger.sqlite3")
    value.register(["new"], OLD_TASKS)

    def reserve(_):
        try:
            return value.reserve("new")
        except BudgetRejected:
            return None

    with ThreadPoolExecutor(max_workers=12) as executor:
        result = list(executor.map(reserve, range(24)))
    assert sum(row is not None for row in result) == 1
    assert value.snapshot()["request_reservations"] == 1


@pytest.mark.parametrize(
    "new_ids", [["same", "same"], ["new_" + str(index) for index in range(28)], [OLD_TASKS[-1]]]
)
def test_registration_rejects_duplicates_over_27_or_any_old_233_task(tmp_path, new_ids):
    value = ledger(tmp_path / "ledger.sqlite3")
    with pytest.raises(BudgetRejected, match="genuinely_new_tasks"):
        value.register(new_ids, OLD_TASKS)
    assert value.snapshot()["request_reservations"] == 0


def test_unregistered_and_old_tasks_cannot_reserve(tmp_path):
    value = ledger(tmp_path / "ledger.sqlite3")
    value.register(["new"], OLD_TASKS)
    for old_or_unknown in [OLD_TASKS[0], OLD_TASKS[-1], "not_registered"]:
        with pytest.raises(BudgetRejected, match="unregistered_or_old_task"):
            value.reserve(old_or_unknown)
    assert value.snapshot()["request_reservations"] == 0


@pytest.mark.parametrize("first_registration", [[], ["new"]])
def test_even_empty_task_registration_is_one_time(tmp_path, first_registration):
    value = ledger(tmp_path / "ledger.sqlite3")
    value.register(first_registration, OLD_TASKS)
    with pytest.raises(BudgetRejected):
        value.register(["second_registration"], OLD_TASKS)


@pytest.mark.parametrize("duplicate_tokens", [211338, 1])
def test_duplicate_prior_debit_ID_is_not_silently_deduplicated(tmp_path, duplicate_tokens):
    with pytest.raises(BudgetRejected):
        ledger(
            tmp_path / "ledger.sqlite3",
            prior=[OLD_DEBIT, {"id": OLD_DEBIT["id"], "tokens": duplicate_tokens}],
        )


@pytest.mark.parametrize("tokens", [-1, 1.5, True, "211338"])
def test_prior_debit_requires_exact_nonnegative_integer(tmp_path, tokens):
    with pytest.raises(BudgetRejected):
        ledger(tmp_path / "ledger.sqlite3", prior=[{"id": "prior", "tokens": tokens}])


def test_only_one_contract_repair_after_successful_known_usage(tmp_path):
    value = ledger(tmp_path / "ledger.sqlite3")
    value.register(["new"], OLD_TASKS)
    with pytest.raises(BudgetRejected):
        value.reserve("new", repair=True)
    first = value.reserve("new")
    with pytest.raises(BudgetRejected):
        value.reserve("new", repair=True)
    assert settle(value, first, usage={"prompt_tokens": 100, "completion_tokens": 20})
    with pytest.raises(BudgetRejected):
        value.reserve("new")
    repair = value.reserve("new", repair=True)
    assert repair["attempt"] == 2
    assert settle(value, repair, usage={"prompt_tokens": 100, "completion_tokens": 20})
    with pytest.raises(BudgetRejected):
        value.reserve("new", repair=True)
    assert value.snapshot()["request_reservations"] == 2


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {"prompt_tokens": 10},
        {"prompt_tokens": True, "completion_tokens": 1},
        {"prompt_tokens": 1, "completion_tokens": -1},
    ],
)
def test_unknown_usage_is_fully_charged_and_not_retryable(tmp_path, usage):
    path = tmp_path / "ledger.sqlite3"
    value = ledger(path)
    value.register(["new"], OLD_TASKS)
    request = value.reserve("new")
    assert not settle(value, request, usage=usage)
    reopened = ledger(path)
    snapshot = reopened.snapshot()
    assert snapshot["conservative_charged_tokens"] == RESERVED
    assert snapshot["cumulative_conservative_debit"] == 211338 + RESERVED
    assert snapshot["reservations"][0]["state"] == "usage_unknown"
    with pytest.raises(BudgetRejected):
        reopened.reserve("new", repair=True)
    with pytest.raises(BudgetRejected):
        reopened.settle(
            request["request_id"],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            outcome="response_received",
        )


def test_usage_breach_records_actual_debit_and_blocks_future_requests(tmp_path):
    value = ledger(tmp_path / "ledger.sqlite3")
    value.register(["new_1", "new_2"], OLD_TASKS)
    request = value.reserve("new_1")
    assert not settle(
        value,
        request,
        usage={"prompt_tokens": INPUT_RESERVATION + 1, "completion_tokens": OUTPUT_CAP},
    )
    snapshot = value.snapshot()
    assert snapshot["budget_breach_count"] == 1
    assert snapshot["cumulative_conservative_debit"] == 211338 + RESERVED + 1
    with pytest.raises(BudgetRejected):
        value.reserve("new_2")


def test_fixed_27_task_54_request_525312_token_boundary(tmp_path):
    value = ledger(tmp_path / "ledger.sqlite3")
    tasks = ["new_" + str(index) for index in range(27)]
    value.register(tasks, OLD_TASKS)
    for task_id in tasks:
        initial = value.reserve(task_id)
        settle(
            value,
            initial,
            usage={"prompt_tokens": INPUT_RESERVATION, "completion_tokens": OUTPUT_CAP},
        )
        repair = value.reserve(task_id, repair=True)
        settle(
            value,
            repair,
            usage={"prompt_tokens": INPUT_RESERVATION, "completion_tokens": OUTPUT_CAP},
        )
    snapshot = value.snapshot()
    assert snapshot["request_reservations"] == 54
    assert snapshot["conservative_charged_tokens"] == 525312
    assert snapshot["cumulative_conservative_debit"] == 211338 + 525312
    with pytest.raises(BudgetRejected):
        value.reserve(tasks[0], repair=True)


def test_protocol_preserves_old_tasks_and_fixed_separate_scopes():
    policy = protocol.policy(panels.policy())
    assert policy["parent_manifest_id"] == protocol.PARENT_MANIFEST
    assert policy["inherited_tasks"] == 233
    assert policy["maximum_new_tasks"] == 27
    assert policy["total_candidate_cap"] == 260
    assert policy["known_prior_rewrite_debit"] == 211338
    assert policy["new_rewrite_request_cap"] == 54
    assert policy["new_rewrite_token_allocation"] == 525312
    assert policy["global_token_cap_unchanged"] == 1000000000
    assert not policy["old_tasks_rewritten"]
    assert not policy["old_unused_209_requests_transferred"]
    assert policy["formal_Teacher_collection_sessions"] == policy["Student_runs"] == 0
    assert policy["evaluation_rewrite_requests"] == 0
    assert len(policy["bounded_source_acquisition"]) == policy["source_HTTP_attempt_cap"] == 2


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_source_redirect_is_rejected_before_any_second_HTTP(code):
    handler = acquisition.NoRedirect()
    attempted = []
    opener = urllib.request.build_opener(handler)
    opener.open = lambda *args, **kwargs: attempted.append(args)
    request = urllib.request.Request(protocol.EXTRA_REPORTS[0]["url"])
    headers = Message()
    headers["Location"] = "https://unregistered.example.invalid/new-report.htm"
    with pytest.raises(urllib.error.HTTPError) as exc:
        opener.error("http", request, io.BytesIO(b"redirect-body"), code, "redirect", headers)
    assert exc.value.code == code
    assert attempted == []


def mock_acquisition(monkeypatch, root, *, mode="success"):
    entity = {"entity_id": "ORCL_US", "cik": "0001341439"}
    bindings = {
        "bound_" + str(index): {
            "entity_id": "ORCL_US",
            "all_equal_source_occurrences": [
                {"record": {"accn": spec["accession"], "filed": spec["filed"], "form": "10-K"}}
            ],
        }
        for index, spec in enumerate(protocol.EXTRA_REPORTS)
    }
    attempts = []

    class FakeParent:
        def __init__(self, *args, **kwargs):
            pass

        def read(self, relative):
            if relative == "native_source_inventory.json":
                return [{"entity": entity}]
            if relative == "native_bindings.json":
                return bindings
            raise AssertionError("unexpected private/source read: " + relative)

    class Response:
        status = 200

        def __init__(self, spec):
            self.url = spec["url"]
            year = "1900" if mode == "invalid_cover" else spec["period_end"][:4]
            self.data = (
                "<html><body>FORM 10-K ORACLE CORPORATION "
                + "For the fiscal year ended May 31, "
                + year
                + "<div>"
                + "synthetic source text " * 6000
                + "</div></body></html>"
            ).encode()
            extra = 1000 if mode == "truncated" else 0
            self.headers = {"Content-Length": str(len(self.data) + extra)}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, amount):
            assert amount == 12000001
            return self.data[:amount]

        def geturl(self):
            return self.url

        def getheader(self, name, default=None):
            return self.headers.get(name, default)

    class Opener:
        def open(self, request, timeout):
            spec = next(row for row in protocol.EXTRA_REPORTS if row["url"] == request.full_url)
            assert timeout == 40
            inputs = root / protocol.OUTPUT / "inputs"
            assert (inputs / "acquisition_started.json").is_file()
            reservation = json.loads(
                (inputs / ("attempt_" + spec["period_end"] + ".json")).read_bytes()
            )
            assert reservation["url"] == request.full_url
            assert reservation["HTTP_attempts"] == 1
            attempts.append(request.full_url)
            if mode == "redirect":
                raise urllib.error.HTTPError(request.full_url, 302, "redirect blocked", {}, None)
            if mode == "timeout":
                raise TimeoutError("synthetic transport timeout; no real HTTP")
            return Response(spec)

    def build_opener(*handlers):
        assert len(handlers) == 1
        assert isinstance(handlers[0], acquisition.NoRedirect)
        return Opener()

    monkeypatch.setattr(acquisition, "Parent", FakeParent)
    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    return attempts


@pytest.mark.parametrize("mode", ["success", "redirect", "timeout"])
def test_source_attempts_are_reserved_once_and_repeated_acquire_cannot_resend(
    tmp_path, monkeypatch, mode
):
    calls = mock_acquisition(monkeypatch, tmp_path, mode=mode)
    result = acquisition.acquire(tmp_path)
    assert calls == [spec["url"] for spec in protocol.EXTRA_REPORTS]
    assert result["request_count"] == 2
    assert result["extra_hosts_or_retries"] == 0
    assert len(result["sources"]) == (2 if mode == "success" else 0)
    with pytest.raises(ValueError, match="one_bounded_attempt_set"):
        acquisition.acquire(tmp_path)
    assert len(calls) == 2


def test_rejected_HTML_keeps_original_HTTP_200_body_and_status(tmp_path, monkeypatch):
    calls = mock_acquisition(monkeypatch, tmp_path, mode="invalid_cover")
    result = acquisition.acquire(tmp_path)
    assert len(calls) == 2 and not result["sources"]
    for row in result["attempts"]:
        assert not row["admitted"]
        assert row["status_code"] == 200
        raw = (tmp_path / row["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["raw_sha256"]
        assert row["reason"] == "acquisition.original_cover_report_period"


def test_declared_Content_Length_truncation_is_not_admitted_as_complete_source(
    tmp_path, monkeypatch
):
    calls = mock_acquisition(monkeypatch, tmp_path, mode="truncated")
    result = acquisition.acquire(tmp_path)
    assert len(calls) == 2
    assert not result["sources"]
    assert all(not row["admitted"] for row in result["attempts"])
    assert all(not row.get("complete_download", False) for row in result["attempts"])
