"""Three inspected public metric reconciliations, not a selected task population.

Both the source-review agent and main agent read each complete public view.
These deliberately illustrative examples were chosen for clear definitions,
not randomly sampled for a supply/yield estimate or assigned to training.
"""

from fractions import Fraction

from .core import record, require

SPECS = (
    {
        "original_id": "K/2012/page_44.pdf-2",
        "index": 309,
        "definition_pointer": ["pre_text", 0],
        "reconciliation_pointer": ["pre_text", 2],
        "definition": (
            "we measure cash flow as net cash provided by operating activities "
            "reduced by expenditures for property additions ."
        ),
        "metric_row": 3,
        "components": [1, 2],
        "years": ["2012", "2011"],
        "expected_values": [["1225", "1001"], ["1758", "1595"], ["-533", "-594"]],
        "scope": (
            "company-defined cash flow, not total investing cash flow; growth-rate row excluded"
        ),
        "unit_pointer": ["table_ori", 0, 0],
        "caveat": (
            "The same public context separately mentions Canadian-dollar debt; "
            "do not infer every dollar is USD."
        ),
    },
    {
        "original_id": "AON/2018/page_41.pdf-1",
        "index": 1329,
        "definition_pointer": ["pre_text", 6],
        "reconciliation_pointer": ["pre_text", 10],
        "definition": (
            "free cash flow we use free cash flow , defined as cash flow provided by operations "
            "minus capital expenditures , as a non-gaap measure of our core operating performance "
            "and cash generating capabilities of our business operations ."
        ),
        "metric_row": 3,
        "components": [1, 2],
        "years": ["2018", "2017"],
        "expected_values": [["1446", "486"], ["1686", "669"], ["-240", "-183"]],
        "scope": (
            "continuing operations only; not discontinued adjusted income "
            "or constant-currency measures"
        ),
        "unit_pointer": ["pre_text", 10],
        "caveat": (
            "Original table scopes every component and total to continuing operations; "
            "preserve that scope."
        ),
    },
    {
        "original_id": "UNP/2017/page_23.pdf-1",
        "index": 1539,
        "definition_pointer": ["pre_text", 8],
        "reconciliation_pointer": ["pre_text", 12],
        "definition": (
            "free cash flow is defined as cash provided by operating activities "
            "less cash used in investing activities and dividends paid ."
        ),
        "metric_row": 4,
        "components": [1, 2, 3],
        "years": ["2017", "2016"],
        "expected_values": [
            ["2162", "2253"],
            ["7230", "7525"],
            ["-3086", "-3393"],
            ["-1982", "-1879"],
        ],
        "scope": "this issuer's free cash flow includes investment cash use and dividends",
        "unit_pointer": ["table_ori", 0, 0],
        "caveat": (
            "Do not substitute the capex-only definition from K or AON; "
            "issuer itself warns definitions differ."
        ),
    },
)


def at(value, pointer):
    for key in pointer:
        value = value[key]
    return value


def amount(value):
    text = value.replace("$", "").replace(",", "").strip()
    negative = text.startswith("(") and text.endswith(")")
    return (-1 if negative else 1) * Fraction(text[1:-1] if negative else text)


def reviewed_examples(rows, draft):
    originals = {row["id"]: row for row in rows}
    assignments = {row["entry_id"]: row for row in draft["rows"]}
    examples = []
    for spec in SPECS:
        row = originals[spec["original_id"]]
        require(
            row["source_split"] == "train" and row["source_record_index"] == spec["index"],
            "examples.original_location",
        )
        require(
            at(row, spec["definition_pointer"]) == spec["definition"],
            "examples.reviewed_definition_unchanged",
        )
        table = row["table_ori"]
        require(table[0][1:3] == spec["years"], "examples.reviewed_year_order")
        metric, components = spec["metric_row"], spec["components"]
        matrix = [[amount(table[r][c]) for c in (1, 2)] for r in [metric, *components]]
        require(
            [[str(x) for x in r] for r in matrix] == spec["expected_values"],
            "examples.reviewed_amounts_unchanged",
        )
        require(
            all(matrix[0][c] == sum(r[c] for r in matrix[1:]) for c in (0, 1)),
            "examples.reviewed_reconciliation",
        )
        differences = [r[0] - r[1] for r in matrix]
        require(differences[0] == sum(differences[1:]), "examples.reviewed_difference")
        evidence = []
        for pointer in [
            spec["definition_pointer"],
            spec["reconciliation_pointer"],
            spec["unit_pointer"],
            *[["table_ori", r, c] for r in [0, metric, *components] for c in (0, 1, 2)],
        ]:
            evidence.append(
                {"pointer": [spec["index"], *pointer], "original_value": at(row, pointer)}
            )
        examples.append(
            record(
                "basis_scale_reviewed_source_example",
                original_id=row["id"],
                original_source_split=row["source_split"],
                original_file_sha256=row["source_file_sha256"],
                original_record_index=spec["index"],
                draft_split=assignments[row["id"]]["draft_split"],
                source_scope=spec["scope"],
                evidence=evidence,
                semantic_relation_basis=(
                    "explicit issuer definition plus complete local reconciliation; "
                    "not numeric subset matching"
                ),
                signed_reporting_convention=(
                    "parenthesized component values are already negative; "
                    "do not subtract them again"
                ),
                endpoint_difference=str(differences[0]),
                signed_component_differences=[str(value) for value in differences[1:]],
                amount_unit=(
                    "millions at this disclosed reporting scale; "
                    "ISO currency binding not certified here"
                ),
                source_relation_review_status="SUPPORTED_AT_DISPLAYED_TABLE_SCOPE",
                historical_issuer_and_ISO_currency_binding="REVIEW_PENDING",
                caveat=spec["caveat"],
                nonrandom_source_review_not_yield_estimation=True,
                reviewers="source-review agent and main agent; nonexperts, not fully independent",
                full_public_table_pre_text_post_text_read=True,
                new_question_constructed=False,
                new_task_certificate_created=False,
                contributes_to_training_dev_or_confirm_task_quota=False,
                review_is_not_Student_evaluation=True,
            )
        )
    return record(
        "basis_scale_source_example_review",
        examples=examples,
        illustrative_sources=len(examples),
        actual_new_certified_tasks=0,
        new_project_provider_API_requests=0,
        source_review_performed_by_assistant_agents=True,
        source_only_review_exposure_recorded=True,
        blinded_source_selection_claimed=False,
    )
