"""Independent auditor controls: original HTML geometry, public targets and evidence tampering."""

import ast
import hashlib
import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import html

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_qa_vnext_catalog_incremental.py"
SPEC = importlib.util.spec_from_file_location("synthetic_incremental_source_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

TABLE = """<table>
<tr><td>Years Ended May 31,</td><td colspan="6"></td></tr>
<tr><td>(Dollars in millions)</td><td colspan="2">2025</td><td></td>
<td colspan="2">2024</td><td></td></tr>
<tr><td>Net cash provided by operating activities</td><td>$</td><td>20,821</td><td></td>
<td>$</td><td>18,673</td><td></td></tr>
<tr><td>Capital expenditures</td><td></td><td>(21,215</td><td>)</td>
<td></td><td>(6,866</td><td>)</td></tr>
<tr><td>Free cash flow</td><td>$</td><td>(394</td><td>)</td><td>$</td><td>11,807</td><td></td></tr>
</table>"""


def originals(source=TABLE):
    grid = audit.original_grid(html.fromstring(source))
    headers, selected = audit.annual_headers(grid)
    return grid, headers, selected


@pytest.mark.parametrize(
    "text,value",
    [
        ("(394)", "-394"),
        ("$ (394 )", "-394"),
        ("($394)", "-394"),
        ("−394", "-394"),
        ("21,215", "21215"),
        ("$ 11,807.5", "11807.5"),
    ],
)
def test_independent_strict_amount_scanner(text, value):
    assert audit.printed_amount(text) == Decimal(value)


@pytest.mark.parametrize(
    "quantity,unit", [("difference", "million USD"), ("relative_change", "percent")]
)
def test_actual_task_target_schema_uses_relative_change_not_the_operator_name(quantity, unit):
    audit.verify_quantity_identity({"quantity": quantity, "unit": unit}, {"unit": unit})


def test_ratio_percent_operator_name_is_not_a_canonical_task_quantity():
    with pytest.raises(ValueError, match="canonical target quantity"):
        audit.verify_quantity_identity(
            {"quantity": "ratio_percent", "unit": "percent"}, {"unit": "percent"}
        )


@pytest.mark.parametrize(
    "text", ["(394", "394)", "(-394)", "1$2", "1,23", "$($90)", "90 70", "—", "-", "90%", "*"]
)
def test_independent_scanner_rejects_ambiguous_or_annotated_number(text):
    with pytest.raises(ValueError):
        audit.printed_amount(text)


def test_independent_original_geometry_binds_negative_total_and_all_symbol_locations():
    grid, headers, selected = originals()
    amount, reference = audit.logical_amount(grid[selected[-1]], headers[0], headers, grid[1])
    assert amount == -394
    assert reference["cells"] == grid[4][1:4]
    certificate = reference["geometry_certificate"]
    assert certificate["body"]["raw_text"] == "(394"
    assert certificate["body"]["cell_xpath"].endswith("/tr[5]/td[3]")
    assert certificate["symbol_bindings"][-1]["cell"]["raw_text"] == ")"
    assert certificate["symbol_bindings"][-1]["outside_annual_header"]
    assert certificate["original_header_row"] == grid[1]
    assert certificate["all_annual_headers"] == headers


def test_independent_reconstruction_does_not_consume_claimed_certificate():
    grid, headers, selected = originals()
    _, claimed = audit.logical_amount(grid[selected[-1]], headers[0], headers, grid[1])
    claimed["geometry_certificate"]["body"]["text"] = "394"
    # Re-read original DOM rather than trusting even a content-hashed altered claim.
    grid2, headers2, selected2 = originals()
    amount, actual = audit.logical_amount(grid2[selected2[-1]], headers2[0], headers2, grid2[1])
    assert amount == -394 and actual != claimed


@pytest.mark.parametrize("marker", ["*", "(1)", "%", "—", "-"])
def test_independent_reconstruction_rejects_replacing_the_close_with_annotation(marker):
    changed = TABLE.replace("<td>(394</td><td>)</td>", f"<td>(394</td><td>{marker}</td>")
    grid, headers, selected = originals(changed)
    with pytest.raises(ValueError):
        audit.logical_amount(grid[selected[-1]], headers[0], headers, grid[1])


def test_independent_reconstruction_rejects_cross_year_body_even_when_closed():
    grid, headers, selected = originals()
    body = grid[selected[-1]][2]
    body["text"], body["stop"] = "(394)", headers[1]["stop"]
    with pytest.raises(ValueError, match="boundary ambiguity"):
        audit.logical_amount(grid[selected[-1]], headers[0], headers, grid[1])


def test_independent_reconstruction_rejects_foreign_header_symbol():
    grid, headers, selected = originals()
    headers[1]["start"] = 3
    with pytest.raises(ValueError, match="another annual header"):
        audit.logical_amount(grid[selected[-1]], headers[0], headers, grid[1])


def test_independent_reconstruction_rejects_shared_indivisible_symbol():
    grid, headers, selected = originals()
    row = grid[selected[-1]]
    row[3]["text"] = ")("
    row[4]["text"] = ""
    row[5]["start"] = 4
    row.pop(4)
    # Original contiguous body/symbol/body geometry has two directional owners.
    with pytest.raises(ValueError, match="shared indivisible symbol"):
        audit.logical_amount(row, headers[0], headers, grid[1])


@pytest.mark.parametrize("unit", ["million USD", "percent"])
def test_public_target_is_independent_of_private_answer_and_supports_negative_FCF(unit):
    grid, headers, selected = originals()
    checker = audit.IncrementalAudit.__new__(audit.IncrementalAudit)
    checker.grids = {"source": grid}
    checker.header_sets = {"source": headers}
    checker.selected_rows = {"source": selected}
    public = {
        "question": (
            "What was the change in Example's company-defined free cash flow from "
            "2024-05-31 to 2025-05-31? Report in "
            + ("percent" if unit == "percent" else "USD millions")
            + "."
        ),
        "sources": [{"source_id": "source", "source_kind": "original_issuer_reconciliation"}],
        "quantity_contract": {"unit": unit, "decimal_places": 2, "rounding": "half away from zero"},
    }
    expected = Decimal(-394 - 11807)
    if unit == "percent":
        expected = 100 * expected / 11807
    assert checker.public_target(public) == expected


def test_public_target_requires_both_actual_endpoint_dates_not_inferred_previous_year():
    grid, headers, selected = originals()
    checker = audit.IncrementalAudit.__new__(audit.IncrementalAudit)
    checker.grids, checker.header_sets, checker.selected_rows = (
        {"source": grid},
        {"source": headers},
        {"source": selected},
    )
    public = {
        "question": (
            "What was the company-defined free cash flow change to 2025-05-31 in USD millions?"
        ),
        "sources": [{"source_id": "source", "source_kind": "original_issuer_reconciliation"}],
        "quantity_contract": {
            "unit": "million USD",
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
    }
    with pytest.raises(ValueError, match="two explicit question endpoint dates"):
        checker.public_target(public)


def test_witness_interpreter_recomputes_real_values_not_output_declaration():
    checker = audit.IncrementalAudit.__new__(audit.IncrementalAudit)
    checker.values = {"a": Decimal(11807), "b": Decimal(-394)}
    witness = {
        "input_bindings": {"previous": "a", "current": "b"},
        "operator_dag": {
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "difference",
                    "inputs": [{"binding": "previous"}, {"binding": "current"}],
                }
            ],
            "output_step": "answer",
        },
        "output": {"value": "999"},
    }
    assert checker.execute_arithmetic(witness) == (Decimal(-12201), {"a", "b"})


def test_manifest_rejects_same_length_byte_tamper(tmp_path):
    member = tmp_path / "native_bindings.json"
    member.write_bytes(b"{}")
    manifest = {
        "schema_version": "finance_qa_vnext_task_build.v1.stage_manifest",
        "members": [{"path": member.name, "bytes": 2, "sha256": hashlib.sha256(b"{}").hexdigest()}],
    }
    manifest["id"] = "stage_manifest:" + hashlib.sha256(audit.canonical(manifest)).hexdigest()
    (tmp_path / "manifest.json").write_bytes(audit.canonical(manifest))
    checker = audit.IncrementalAudit.__new__(audit.IncrementalAudit)
    checker.stage, checker.counts = tmp_path, {}
    checker.verify_manifest()
    member.write_bytes(b"[]")
    with pytest.raises(ValueError, match="member hash"):
        checker.verify_manifest()


def test_auditor_imports_no_generation_or_execution_module():
    tree = ast.parse(SCRIPT.read_text())
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(x.name for x in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(
        any(
            word in name
            for word in ("issuer_tables", "factory", "binding_executor", "plan_executor")
        )
        for name in imported
    )


def test_verify_entrypoint_checks_a_complete_empty_increment_without_production(tmp_path):
    directory = tmp_path / "incremental"
    directory.mkdir()

    def record(kind, **values):
        body = {"schema_version": "finance_qa_vnext_task_build.v1." + kind, **values}
        return {**body, "id": kind + ":" + hashlib.sha256(audit.canonical(body)).hexdigest()}

    def save(name, value):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audit.canonical(value))

    names = (
        "raw_objects standardized_facts source_documents source_metric_definitions "
        "canonical_entities atomic_facts qa_samples qa_candidates qa_operation_plans "
        "qa_builds qa_graph_patterns qa_quality_checks derived_facts kg_builds kg_nodes"
    ).split()
    for name in names:
        save("parents/" + name + "/0000.json", [])
    save("parent_table_inventory.json", [{"table": name, "row_count": 0} for name in names])
    save("native_bindings.json", {})
    save("issuer_source_tables.json", {"tables": [], "observations": []})
    save("all_leaf_usage.json", {})
    save("catalog.json", record("fixed_task_catalog", tasks=[]))
    save("new_tasks/pattern_compilations.json", [])
    save(
        "stage_freeze.json",
        record(
            "incremental_stage_freeze",
            git_commit="synthetic-control-only",
            rule={"source_split": {"salt": "fixture:", "buckets": 55, "train": [0, 9]}},
        ),
    )
    members = [
        {
            "path": str(path.relative_to(directory)),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(directory.rglob("*.json"))
    ]
    save("manifest.json", record("stage_manifest", members=members))
    result = audit.verify(tmp_path, "incremental")
    assert result["status"] == "passed" and result["counts"]["source_recomputed_tasks"] == 0
    assert result["old_233_tasks_reaudited"] is False
    assert result["production_artifacts_changed"] is False
    assert result["model_calls"] == 0


def unmaterialized_fixture(tmp_path, *, downloaded=False, tamper=None):
    directory = tmp_path / "bridge/incremental"
    directory.mkdir(parents=True)
    relative = (
        "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/fixture/inputs/"
        if downloaded
        else "sec/filings/"
    ) + "cik=0001341439/accession=fixture/report.htm"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    data = TABLE.encode()
    path.write_bytes(data)
    pin = {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    raw = {
        "raw_object_id": "unmaterialized_raw",
        "object_type": "html",
        "storage_uri": relative if downloaded else "/workspace/Data Synthesis/" + relative,
        "content_size_bytes": len(data),
        "content_sha256": pin["sha256"],
    }
    if tamper == "raw_and_bytes":
        # Matching the inventory's rewritten hash is insufficient: frozen bytes disagree.
        changed = data.replace(b"20,821", b"20,822")
        path.write_bytes(changed)
        raw["content_sha256"] = hashlib.sha256(changed).hexdigest()
    elif tamper == "frozen_sha":
        pin["sha256"] = "0" * 64
    elif tamper == "frozen_path":
        pin["path"] += ".wrong"

    def record(kind, **values):
        body = {"schema_version": "finance_qa_vnext_task_build.v1." + kind, **values}
        return {**body, "id": kind + ":" + hashlib.sha256(audit.canonical(body)).hexdigest()}

    parent = record(
        "catalog_bridge_freeze",
        source_files=(
            [{"path": "historical_panel.json", "sha256": "metadata_only_pin", "id": "history"}]
            + ([] if downloaded else [pin])
        ),
    )
    inputs = record(
        "catalog_bridge_input_freeze",
        stage_freeze_id="unrelated-freeze" if tamper == "freeze_join" else parent["id"],
        members=[pin] if downloaded else [],
    )
    frozen = record("incremental_task_freeze", stage_freeze_id=parent["id"], input_freeze=inputs)
    (directory.parent / "stage_freeze.json").write_bytes(audit.canonical(parent))
    (directory / "stage_freeze.json").write_bytes(audit.canonical(frozen))
    checker = audit.IncrementalAudit.__new__(audit.IncrementalAudit)
    checker.root, checker.stage = tmp_path, directory
    checker.raw, checker.dom, checker.counts = {}, {}, {}
    issuer = {
        "tables": [{"raw_object_id": raw["raw_object_id"]}],
        "sources": [{"raw_object": raw}],
    }
    return checker, issuer


@pytest.mark.parametrize("downloaded", [False, True])
def test_unmaterialized_table_is_double_pinned_but_not_fabricated_as_raw_parent(
    tmp_path, downloaded
):
    checker, issuer = unmaterialized_fixture(tmp_path, downloaded=downloaded)
    originals = checker.unmaterialized_sources(issuer)
    assert "unmaterialized_raw" in originals and "unmaterialized_raw" in checker.dom
    assert checker.raw == {}
    assert checker.counts["unmaterialized_table_original_files_separately_checked"] == 1
    grid = audit.original_grid(checker.dom["unmaterialized_raw"])
    assert audit.annual_headers(grid)[0][0]["period_end"] == "2025-05-31"


@pytest.mark.parametrize("downloaded", [False, True])
@pytest.mark.parametrize("tamper", ["raw_and_bytes", "frozen_sha", "frozen_path", "freeze_join"])
def test_unmaterialized_original_requires_both_inventory_and_frozen_input_proof(
    tmp_path, downloaded, tamper
):
    checker, issuer = unmaterialized_fixture(tmp_path, downloaded=downloaded, tamper=tamper)
    with pytest.raises(ValueError):
        checker.unmaterialized_sources(issuer)
    assert checker.raw == {}
