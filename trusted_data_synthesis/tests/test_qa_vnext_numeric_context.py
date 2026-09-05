from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_UP, localcontext
from pathlib import Path

import pytest

from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.catalog import (
    FinanceQACatalog,
    catalog_operation_registry,
)
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import (
    ProgramTaskAdapter,
    public_program_answer,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import record
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import (
    SHARE_FAMILY,
    ShareTaskAdapter,
    add_share_operations,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_RATIO = "0.93508458258836473662494842525099711181405583826159"
EXPECTED_PERCENT = "93.508458"


@pytest.mark.parametrize("rounding", [ROUND_DOWN, ROUND_UP])
@pytest.mark.parametrize("support", ["disclosed_total", "reconstructed_total"])
def test_share_executor_oracle_and_final_ignore_ambient_rounding(
    tmp_path: Path, rounding: str, support: str
) -> None:
    registry = catalog_operation_registry()
    add_share_operations(registry)
    adapter = ShareTaskAdapter(
        REPO_ROOT,
        registry,
        record("test_resolution", task_type=SHARE_FAMILY),
    )
    callback = PublicFixtureCallback(support_preference=support)
    runtime = PublicQARuntime(adapter, callback, tmp_path / "share")
    assert adapter.context["numeric"]["rounding"] == "ROUND_HALF_EVEN"

    with localcontext() as ambient:
        ambient.rounding = rounding
        ambient.prec = 6
        session = runtime.run()
        assert ambient.rounding == rounding
        assert ambient.prec == 6
        assert session["final"] is not None
        final = session["final"]
        assert final["answer"]["result"] == {"value": EXPECTED_PERCENT, "unit": "percent"}
        assert final["qa_validation"]["qa_valid"]
        assert adapter.verify_final(final["answer"], session["claims"])["qa_valid"]

        ratio_event = next(
            event
            for event in session["events"]
            if event.get("execution", {}).get("operation") == "share_ratio"
        )
        selected = ratio_event["execution"]["selected_action"]
        prepared = adapter.prepare(selected, session["claims"])
        observed = ratio_event["execution"]["proposition"]
        assert observed["output"]["value"] == EXPECTED_RATIO
        assert adapter.execute(prepared) == observed
        assert adapter.verify_execution(prepared, observed)
        numeric_oracle = registry.require("share_ratio").oracle_verifier
        assert numeric_oracle.verify(
            prepared["inputs"], prepared["parameters"], {"value": EXPECTED_RATIO}
        ).passed
        assert not numeric_oracle.verify(
            prepared["inputs"],
            prepared["parameters"],
            {"value": EXPECTED_RATIO[:-1] + "8"},
        ).passed

    operations = [
        event["execution"]["operation"] for event in session["events"] if "execution" in event
    ]
    assert operations == (
        ["relation_sum", "share_ratio", "scale_percent"]
        if support == "reconstructed_total"
        else ["share_ratio", "scale_percent"]
    )
    assert all(
        event["observation"]["independent_output_valid"]
        for event in session["events"]
        if "observation" in event
    )


@pytest.mark.parametrize("rounding", [ROUND_DOWN, ROUND_UP])
@pytest.mark.parametrize("task_type", ["registered_ratio", "temporal_growth"])
def test_program_execution_oracle_projection_and_final_ignore_ambient_context(
    tmp_path: Path, rounding: str, task_type: str
) -> None:
    registry = catalog_operation_registry()
    catalog = FinanceQACatalog(registry)
    cases, _ = catalog.frozen_source_cases(REPO_ROOT, task_types=(task_type,))
    assert len(cases) == 1
    adapter = ProgramTaskAdapter(cases[0], registry)
    numeric = adapter.context["numeric"]
    assert numeric["precision"] == 28
    assert numeric["rounding"] == "ROUND_HALF_EVEN"
    assert numeric["share_numeric_contract_reused"] is False
    baseline = PublicQARuntime(adapter, PublicFixtureCallback(), tmp_path / "baseline").run()
    assert baseline["final"] is not None
    expected_result = baseline["final"]["answer"]["result"]
    if task_type == "registered_ratio":
        assert expected_result == {"value": "0.05859003425857716047175276608"}
    baseline_propositions = [
        event["execution"]["proposition"] for event in baseline["events"] if "execution" in event
    ]

    runtime = PublicQARuntime(adapter, PublicFixtureCallback(), tmp_path / "ambient")
    with localcontext() as ambient:
        ambient.prec = 6
        ambient.rounding = rounding
        session = runtime.run()
        assert ambient.prec == 6
        assert ambient.rounding == rounding
        assert session["final"] is not None
        final = session["final"]
        assert final["answer"]["result"] == expected_result
        assert final["qa_validation"]["qa_valid"]
        assert public_program_answer(adapter.context, session["claims"]) == expected_result
        assert adapter.verify_final(final["answer"], session["claims"])["qa_valid"]
        propositions = []
        for event in session["events"]:
            if "execution" not in event:
                continue
            execution = event["execution"]
            prepared = adapter.prepare(execution["selected_action"], session["claims"])
            proposition = execution["proposition"]
            assert adapter.execute(prepared) == proposition
            assert adapter.verify_execution(prepared, proposition)
            assert event["observation"]["independent_output_valid"]
            propositions.append(proposition)
        assert propositions == baseline_propositions
        assert session["claims"] == baseline["claims"]
