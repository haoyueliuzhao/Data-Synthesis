"""Current Flash contract controls, all synthetic/offline and no old replay."""

import ast
import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.capsule import (
    capsule_files,
)
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.costs import cost_summary
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.model_contract import (
    ACCEPTED_RESPONSE_MODELS,
    REQUESTED_MODEL,
    response_model_matches,
)
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.plan import (
    MODEL,
    MODEL_CATALOG_SHA256,
    OUTPUT,
    PACKAGE,
    PRIOR_OUTPUT,
    condition,
    read_json,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import (
    capsule_files as parent_capsule_files,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.stage import public_document

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "trusted_data_synthesis/src/trusted_synthesis/experiments"


def test_caller_and_response_contract_matches_live_catalog_snapshot():
    raw = (ROOT / PACKAGE / "model_catalog_snapshot.json").read_bytes()
    assert sha(raw) == MODEL_CATALOG_SHA256
    catalog = json.loads(raw)
    assert MODEL == REQUESTED_MODEL == "deepseek-flash"
    assert ACCEPTED_RESPONSE_MODELS == ("deepseek-flash",)
    assert MODEL in {row["id"] for row in catalog["models"]}
    assert condition()["accepted_response_models"] == [MODEL]


@pytest.mark.parametrize(
    "observed",
    ["deepseek-v4-pro", "deepseek-pro", "deepseek-v4-flash", "deepseek-flash-unknown", None],
)
def test_no_pro_fallback_wildcard_or_unregistered_alias(observed):
    assert not response_model_matches(MODEL, observed)
    assert not response_model_matches("deepseek-v4-pro", MODEL)


def test_unchanged_panel_and_prior_batch_separate():
    panel = Panel(ROOT)
    assert OUTPUT != PRIOR_OUTPUT
    for key, task in panel.tasks.items():
        assert public_document(task) == read_json(
            ROOT / PRIOR_OUTPUT / f"preparation/public/{key}.json"
        )
    assert condition()["previous_72_sessions_not_resumed_regraded_or_pooled"]


def test_capsule_preserves_T_calculator_projection_and_isolation():
    old, current = parent_capsule_files(ROOT, "T"), capsule_files(ROOT)
    assert set(current) == {*old, "model_contract.py"}
    for key in ("common.py", "calculator.py", "projection.py", "isolate.py"):
        assert current[key] == old[key]
    assert current["worker.py"] != old["worker.py"]


class RestoreLegacyIdentity(ast.NodeTransformer):
    """Normalize only the explicitly authorized identity edits for AST comparison."""

    def __init__(self):
        self.source_checks = self.worker_checks = 0

    def visit_ImportFrom(self, item):
        return None if item.module == "model_contract" else item

    def visit_FunctionDef(self, item):
        item = self.generic_visit(item)
        if item.name == "generate":
            assert isinstance(item.args.defaults[-1], ast.Name)
            assert item.args.defaults[-1].id == "REQUESTED_MODEL"
            item.args.defaults[-1] = ast.Constant(value="deepseek-v4-flash")
        return item

    def visit_UnaryOp(self, item):
        if (
            isinstance(item.op, ast.Not)
            and isinstance(item.operand, ast.Call)
            and isinstance(item.operand.func, ast.Name)
            and item.operand.func.id == "response_model_matches"
        ):
            assert (
                ast.unparse(item.operand) == "response_model_matches(model, envelope.get('model'))"
            )
            self.worker_checks += 1
            return ast.parse(
                (
                    "envelope.get('model') not in {model, model + ('-0731' if "
                    "model.endswith('flash') else '-0813')}"
                ),
                mode="eval",
            ).body
        return self.generic_visit(item)

    def visit_Call(self, item):
        if isinstance(item.func, ast.Name) and item.func.id == "response_model_matches":
            assert ast.unparse(item) == "response_model_matches(MODEL, projection['model'])"
            self.source_checks += 1
            return ast.parse("projection['model'] in {MODEL, MODEL + '-0731'}", mode="eval").body
        if (
            isinstance(item.func, ast.Attribute)
            and item.func.attr == "add_argument"
            and item.args
            and isinstance(item.args[0], ast.Constant)
            and item.args[0].value == "--model"
        ):
            assert (
                ast.unparse(item)
                == (
                    "parser.add_argument('--model', choices=[REQUESTED_MODEL], "
                    "default=REQUESTED_MODEL)"
                )
            )
            return ast.parse(
                (
                    "parser.add_argument('--model', choices=['deepseek-v4-flash', "
                    "'deepseek-v4-pro'], default='deepseek-v4-flash')"
                ),
                mode="eval",
            ).body
        return self.generic_visit(item)


def test_worker_only_identity_related_AST_changes():
    original = ast.parse(
        (EXPERIMENTS / "finance_qa_vnext_thinking_comparison/online/worker.py").read_text()
    )
    current = ast.parse((ROOT / PACKAGE / "online_worker.py").read_text())
    restore = RestoreLegacyIdentity()
    assert ast.dump(restore.visit(current)) == ast.dump(original)
    assert restore.worker_checks == 2 and restore.source_checks == 0


def test_source_binder_only_identity_related_AST_changes():
    original = ast.parse(
        (EXPERIMENTS / "finance_qa_vnext_open_support_exploration/source.py").read_text()
    )
    current = ast.parse((ROOT / PACKAGE / "source.py").read_text())
    restore = RestoreLegacyIdentity()
    assert ast.dump(restore.visit(current)) == ast.dump(original)
    assert restore.source_checks == 1 and restore.worker_checks == 0


@pytest.mark.parametrize(
    "returned_model,expected_tools,expected_terminal",
    [
        ("deepseek-flash", 1, "model_final"),
        ("deepseek-v4-pro", 0, "unknown_transport_or_condition"),
    ],
)
def test_synthetic_HTTP_envelope_reaches_tools_only_for_current_flash(
    tmp_path, returned_model, expected_tools, expected_terminal
):
    # This mocks the transport in a separate process; these are constructed unit
    # fixtures, NOT real provider responses or experiment observations.
    bundle = DurableStore(tmp_path / "bundle")
    for name, raw in capsule_files(ROOT).items():
        bundle.write(name, raw)
    output = tmp_path / "synthetic_session"
    script = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import worker
from common import encode
responses = [
    {'tool':'calculate','arguments':{'expression':'10-4'}},
    {'final':{'value':'6','unit':'USD_million','result_id':'tool:1'}},
]
calls = []
def mocked_transport(body, credential):
    request = json.loads(body)
    assert request['model'] == 'deepseek-flash'
    calls.append(request)
    envelope = {'id':'synthetic-not-provider-' + str(len(calls)),
                'object':'chat.completion','model':sys.argv[3],
                'choices':[{'index':0,'finish_reason':'stop',
                            'message':{'role':'assistant','content':encode(responses[len(calls)-1]).decode()}}]}
    return {'status':200,'error':None,'elapsed_ns':0,'body':encode(envelope)}
worker.https_request = mocked_transport
document = {'id':'synthetic-document','task_id':'synthetic-task','question':'unit control',
            'numeric_catalog':[],'segments':{}}
result = worker.generate(document, Path(sys.argv[2]), credential='unit-test-placeholder')
print(json.dumps({'terminal':result['terminal'],'tools':result['tool_calls'],
                  'mocked_transport_calls':len(calls),'real_provider_calls':0}))
"""
    completed = subprocess.run(
        [
            "/usr/bin/python3",
            "-I",
            "-S",
            "-B",
            "-c",
            script,
            str(bundle.root),
            str(output),
            returned_model,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["tools"] == expected_tools and result["terminal"] == expected_terminal
    assert result["real_provider_calls"] == 0


def test_cost_aggregation_uses_current_model_not_old_hardcoded_name(tmp_path):
    store = DurableStore(tmp_path / "online")
    store.json(
        "launch.json",
        {
            "registrations": [
                {"label": "T_X1_01", "task_key": "X1", "arm": "T", "requested_model": MODEL}
            ]
        },
    )
    report = cost_summary(store.root)
    assert report["rows"][0]["requested_model"] == "deepseek-flash"
    assert report["aggregate"]["reserved_attempts"] == 0
