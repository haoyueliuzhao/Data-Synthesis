"""New bounded-study controls. Synthetic Worker transport only; no real provider or old replay."""

import ast
import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.capsule import (
    capsule_files as prior_capsule,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.archive import export
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.capsule import (
    capsule_files,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.evaluate import qualify
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.exploration import (
    R_evidence_chain,
    complete_class,
    target_prototypes,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.measurement import (
    measure,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.panel import (
    CLARIFIED_TASK_ID,
    Panel,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    ARMS,
    LABELS,
    OUTPUT,
    PACKAGE,
    PARENT,
    PARENT_PACKAGE,
    QUANTITY_SUFFIX,
    SOFT_SUFFIX,
    SYSTEMS_NEW,
    TASKS,
    condition,
    policy,
    public_quantity_context,
    read_json,
    record,
    registrations,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.projection import (
    project_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.quantity import (
    interpret_final,
    score_quantity,
)
from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.source import (
    bind_execution_prefix,
    bind_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.evaluate import (
    REVIEW_FIELDS,
    audit_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def panel():
    return Panel(ROOT)


@pytest.fixture(scope="module")
def prototypes(panel):
    return target_prototypes(panel)


def test_only_three_tasks_original_X1_X2_and_new_clear_X3_identity(panel):
    assert tuple(panel.tasks) == TASKS
    for key in ("X1", "X2"):
        assert panel.public[key] == read_json(ROOT / PARENT / f"preparation/public/{key}.json")
    old = read_json(ROOT / PARENT / "preparation/public/X3.json")
    new = panel.public["X3C"]
    assert new["task_id"] == CLARIFIED_TASK_ID != old["task_id"]
    assert new["question"] != old["question"]
    for key in ("source", "segments", "numeric_catalog", "filename", "indexing"):
        assert new[key] == old[key]
    assert "December 29, 2007" in new["question"]
    assert "December 27, 2008" in new["question"]
    assert panel.private["X3C"]["reference_exact_value"] == "439/5"


def test_single_N_E_public_factor_and_no_task_solution_in_soft_suffix():
    assert SYSTEMS_NEW["N"] == SYSTEMS["T"] + "\n\n" + QUANTITY_SUFFIX
    assert SYSTEMS_NEW["E"] == SYSTEMS_NEW["N"] + "\n\n" + SOFT_SUFFIX
    assert not any(char.isdigit() for char in SOFT_SUFFIX)
    for prohibited in ("source:", "46.4", "87.8", "48.3", "X1", "X2", "X3", "only R"):
        assert prohibited not in SOFT_SUFFIX
    assert condition("N")["id"] != condition("E")["id"]


def test_exactly_48_preordered_interleaved_independent_registrations(panel):
    rows = registrations(panel.public)
    assert [r["label"] for r in rows] == list(LABELS)
    assert len(rows) == len({r["review_id"] for r in rows}) == 48
    for first, second in zip(rows[::2], rows[1::2], strict=True):
        assert (first["arm"], second["arm"]) == ARMS
        assert first["task_key"] == second["task_key"]
        assert first["replicate"] == second["replicate"]
    for wave in (1, 2):
        counts = Counter((r["arm"], r["task_key"]) for r in rows if r["wave"] == wave)
        assert counts == {(arm, key): 4 for arm in ARMS for key in TASKS}
    assert policy()["maximum_generation_requests"] == 1536
    assert (
        policy()["training_runs"] == policy()["student_sessions"] == policy()["auxiliary_NLL"] == 0
    )
    assert policy()["tokenizer_or_Student_weight_loading"] is False


@pytest.mark.parametrize("arm", ARMS)
def test_current_Flash_Worker_tools_transport_and_isolation_reused_byte_for_byte(arm):
    before, after = prior_capsule(ROOT), capsule_files(ROOT, arm)
    assert set(before) == set(after)
    for name in before:
        if name != "common.py":
            assert before[name] == after[name]
    assert after["common.py"].startswith(before["common.py"])
    namespace = {}
    exec(compile(after["common.py"], "synthetic_common", "exec"), namespace)
    assert namespace["SYSTEM"] == SYSTEMS_NEW[arm]


def test_normalization_algorithm_unchanged_and_no_equal_number_source_lookup():
    old = ast.parse((ROOT / PARENT_PACKAGE / "projection.py").read_text())
    new = ast.parse((ROOT / PACKAGE / "projection.py").read_text())
    for name in ("_pointer", "_number", "_public_evidence", "_scalar", "_normalize_call"):
        first = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == name)
        second = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == name)
        assert ast.dump(first) == ast.dump(second)


@pytest.mark.parametrize("task", TASKS)
def test_D_R_full_prototypes_stay_distinct_and_condition_specific(prototypes, task):
    for arm in ARMS:
        targets = prototypes["tasks"][arm][task]
        for route in ("D", "R"):
            prototype = targets[route]
            projection = {
                "status": "MAPPED",
                "behavior_signature": prototype["signature"],
                "behavior_key": prototype["behavior_key"],
            }
            assert complete_class(projection, targets) == "PURE_" + route
        assert targets["D"]["behavior_key"] != targets["R"]["behavior_key"]
    assert (
        prototypes["tasks"]["N"][task]["R"]["behavior_key"]
        != prototypes["tasks"]["E"][task]["R"]["behavior_key"]
    )


def _call(route, *, mention_R=False, invalid_unit=False):
    if route == "D":
        variables = {
            "later": {"value": "426.6", "source": "source:t4c1n0", "unit": "USD millions"},
            "earlier": {"value": "380.2", "source": "source:t1c1n0", "unit": "USD millions"},
        }
        expression = "later - earlier"
        message = "I use Entergy Mississippi net revenue for 2003 minus 2002, in USD millions."
    else:
        variables = {
            "base_rates": {"value": "48.3", "source": "source:t2c1n0", "unit": "USD millions"},
            "other": {"value": "-1.9", "source": "source:t3c1n0", "unit": "USD millions"},
        }
        expression = "base_rates + other"
        message = (
            "I use the 2003-versus-2002 net revenue change components: base rates "
            "plus the signed other movement, in USD millions."
        )
    if mention_R:
        message += (
            " The base-rate and other movements also sum to the change; I only "
            "execute the endpoint difference."
        )
        variables.update(_call("R")["arguments"]["variables"])
    if invalid_unit:
        for value in variables.values():
            value["unit"] = "EUR million"
        message = message.replace("USD millions", "EUR million")
    return {
        "message": message,
        "tool": "calculate",
        "arguments": {"expression": expression, "variables": variables},
    }


def _synthetic_worker(tmp_path, panel, arm, mode):
    root = tmp_path / "fixture_root"
    prep = DurableStore(root / OUTPUT / "preparation")
    prep.json("public/X1.json", panel.public["X1"])
    bundle = DurableStore(tmp_path / "bundle")
    for name, raw in capsule_files(ROOT, arm).items():
        bundle.write(name, raw)
    if mode == "D_mention_only":
        responses = [_call("D", mention_R=True)]
    elif mode == "revision_R":
        responses = [
            {
                "message": "Unintended year numeral subtraction.",
                "tool": "calculate",
                "arguments": {"expression": "2006 - 2005"},
            },
            _call("R"),
        ]
        responses[1]["message"] += (
            " I correct the previous year-literal inputs to the actual financial component amounts."
        )
    elif mode == "dual":
        responses = [_call("R"), _call("D")]
        responses[1]["message"] += (
            " I independently check the component calculation using the endpoint difference."
        )
    else:
        responses = [_call("R", invalid_unit=mode == "wrong_currency_R")]
    if mode != "no_Final_R":
        responses.append(
            {
                "final": {
                    "value": "46.4",
                    "unit": "EUR million" if mode == "wrong_currency_R" else "$ in millions",
                    "answer": "The net revenue change is an increase of 46.4 million "
                    + ("EUR." if mode == "wrong_currency_R" else "USD."),
                    "result_id": "tool:2" if mode in {"revision_R", "dual"} else "tool:1",
                    "check": "The independently executed component result agrees."
                    if mode == "dual"
                    else None,
                }
            }
        )
    fixture = DurableStore(tmp_path / "fixture")
    fixture.json("responses.json", responses)
    fixture.json("public.json", panel.public["X1"])
    label = f"{arm}_X1_01"
    directory = root / OUTPUT / "online/sessions" / label
    script = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import worker
from common import encode
responses = json.loads(Path(sys.argv[3]).read_bytes())
document = json.loads(Path(sys.argv[4]).read_bytes())
calls = []
def mocked_transport(body, credential):
    request = json.loads(body)
    assert request['model'] == 'deepseek-flash'
    calls.append(request)
    if len(calls) > len(responses):
        return {'status':500,'error':'synthetic_failure_after_recorded_execution',
                'elapsed_ns':0,'body':b'{}'}
    envelope = {
        'id':'synthetic-not-provider-' + str(len(calls)), 'object':'chat.completion',
        'model':'deepseek-flash',
        'choices':[{'index':0,'finish_reason':'stop',
                    'message':{'role':'assistant',
                               'content':encode(responses[len(calls)-1]).decode()}}],
        'usage':{'prompt_tokens':100,'completion_tokens':10,'total_tokens':110,
                 'prompt_cache_hit_tokens':90,'prompt_cache_miss_tokens':10,
                 'completion_tokens_details':{'reasoning_tokens':1}},
    }
    return {'status':200,'error':None,'elapsed_ns':0,'body':encode(envelope)}
worker.https_request = mocked_transport
result = worker.generate(document, Path(sys.argv[2]), credential='unit-test-placeholder')
print(json.dumps({'terminal':result['terminal'],'real_provider_calls':0}))
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
            str(directory),
            str(fixture.root / "responses.json"),
            str(fixture.root / "public.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)["real_provider_calls"] == 0
    result = read_json(directory / "result.json")
    raw = {int(p.name[:3]): p.read_text() for p in (directory / "turns").glob("*_assistant.raw")}
    audit = audit_session(
        directory, panel.public["X1"], panel.private["X1"], expected_system=SYSTEMS_NEW[arm]
    )
    interpreted = interpret_final(audit["raw_final"], public_quantity_context())
    audit = {
        **audit,
        "label": label,
        "task_key": "X1",
        "arm": arm,
        "review_id": "synthetic_review",
        "automatic_quantity": score_quantity(interpreted, "232/5", public_quantity_context()),
    }
    return root, result, raw, audit


def _review(result, raw, audit, mode):
    selected = None if mode == "no_Final_R" else result["final"]["result_id"]
    final_index = audit["first_final_index"]

    def evidence(index):
        return {"response_index": index, "quote": raw[index]}

    selected_index = next(
        (c["response_index"] for c in audit["calculations"] if c["call_id"] == selected), 0
    )
    interpreted = audit["automatic_quantity"]["interpretation"]
    fields = {}
    for field in (*REVIEW_FIELDS, "final_answer_consistency"):
        is_final = field in {"publication_alignment", "final_answer_consistency"}
        index = final_index if is_final else selected_index
        status = "UNDETERMINED" if index is None else "PASS"
        if mode == "wrong_currency_R" and field in {"unit_handling", "publication_alignment"}:
            status = "FAIL"
        fields[field] = {
            "status": status,
            "evidence": [] if index is None else [evidence(index)],
            "explanation": (
                "Constructed control with explicit source-role and interval declarations."
            ),
        }
    review = {
        **fields,
        "published_value": interpreted.get("published_value"),
        "published_unit": interpreted.get("published_unit"),
        "answer_override_evidence": [],
        "secondary_answer_values": [],
        "answer_calculation_id": selected,
        "answer_calculation_unit": "USD_million",
        "planning_observations": {
            "text": "Constructed finite test only.",
            "evidence": [evidence(i) for i in raw],
        },
        "R_mention": {
            "status": "CONFIRMED",
            "evidence": [evidence(0)],
            "explanation": "The actual synthetic public message gives the component relation.",
        },
        "R_Final_link": {
            "status": "NOT_OBSERVED"
            if mode in {"D_mention_only", "no_Final_R", "wrong_currency_R"}
            else "CONFIRMED",
            "evidence": [] if final_index is None else [evidence(final_index)],
            "explanation": "Actual synthetic Final support, not a correct-number inference.",
        },
        "call_semantics": {},
        "mapping": {
            "occurrences": {},
            "event_annotations": [],
            "revisions": [],
            "cross_checks": [],
        },
    }
    for event in result["events"]:
        index, call = event["response_index"], event["tool_call"]
        role = "Final" if event["final"] else "answer_calculation"
        if call:
            args = call["arguments"]
            nodes = ast.parse(args["expression"], mode="eval").body
            occurrences = {}
            for address, node in (("body.left", nodes.left), ("body.right", nodes.right)):
                if isinstance(node, ast.Name):
                    sid = args["variables"][node.id]["source"]
                    occurrences[address] = {
                        "kind": "source",
                        "source_id": sid,
                        "attribution": "model_declaration",
                        "declaration_pointer": ["variables", node.id, "source"],
                        "evidence": [evidence(index)],
                        "role": "Explicit source-role " + node.id,
                        "period": "2003 versus 2002",
                        "unit": "USD_million",
                    }
                else:
                    occurrences[address] = {
                        "kind": "constant",
                        "value": str(node.value),
                        "reason": "Actual unintended literal year numeral, not a source value.",
                        "evidence": [evidence(index)],
                    }
            review["mapping"]["occurrences"][call["id"]] = occurrences
            review["call_semantics"][call["id"]] = {
                field: {
                    "status": "FAIL"
                    if mode == "wrong_currency_R" and field == "unit_handling"
                    else "PASS",
                    "evidence": [evidence(index)],
                    "explanation": "Explicit synthetic source role.",
                }
                for field in REVIEW_FIELDS[:3]
            }
            if mode == "revision_R" and index == 0:
                role = "superseded_calculation"
            elif mode == "dual" and index == 0:
                role = "cross_check_calculation"
        review["mapping"]["event_annotations"].append(
            {
                "response_index": index,
                "role": role,
                "interpretation": "Original synthetic event.",
                "evidence": [evidence(index)],
            }
        )
    if mode == "revision_R":
        review["mapping"]["revisions"].append(
            {
                "before_index": 0,
                "after_index": 1,
                "change_kind": "substantive",
                "semantic_key": {
                    "from": "unintended_year_literals",
                    "to": "source_component_amounts",
                },
                "interpretation": (
                    "The previous successful calculation used the wrong operand domain."
                ),
                "evidence": [evidence(0), evidence(1)],
            }
        )
    if mode == "dual":
        review["mapping"]["cross_checks"].append(
            {
                "call_id": "tool:1",
                "evidence": [evidence(1), evidence(final_index)],
                "interpretation": (
                    "Actual independent component calculation used to check endpoint answer."
                ),
            }
        )
    return review


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize(
    "mode,expected_class,valid",
    [
        ("R", "PURE_R", True),
        ("D_mention_only", "PURE_D", True),
        ("revision_R", "R_WITH_SUBSTANTIVE_REVISION", True),
        ("dual", "D_WITH_CROSS_CHECK", True),
        ("wrong_currency_R", "NOT_JOINT_VALID", False),
        ("no_Final_R", "NOT_JOINT_VALID", False),
    ],
)
def test_synthetic_end_to_end_exact_execution_source_Final_and_full_class(
    tmp_path, panel, prototypes, arm, mode, expected_class, valid
):
    root, result, raw, audit = _synthetic_worker(tmp_path, panel, arm, mode)
    review = _review(result, raw, audit, mode)
    row = qualify(audit, review, raw)
    assert row["formula_driven_trace_verified"] is valid
    assert row["answer"]["V_format"] == "FAIL"
    if valid:
        session = bind_session(root, row)
        projection = project_session(session, review["mapping"], panel.private["X1"]["goal_scope"])
        assert projection["status"] == "MAPPED", projection.get("reason")
    else:
        session = bind_execution_prefix(root, row)
        projection = None
    chain = R_evidence_chain(session, review, prototypes["tasks"][arm]["X1"], projection)
    assert chain["complete_behavior_label"] == expected_class
    assert chain["public_R_mention"]["status"] == "CONFIRMED"
    assert chain["R_execution_status"] == (
        "NOT_OBSERVED" if mode == "D_mention_only" else "CONFIRMED"
    )
    assert chain["valid_pure_R"] is (mode == "R")
    if mode == "D_mention_only":
        resolved = result["events"][0]["tool_call"]["output"]["result"]["resolved_variables"]
        assert set(resolved) == {"later", "earlier"}
    if mode == "wrong_currency_R":
        assert chain["R_source_relation_status"] == "FAIL"
        assert chain["R_Final_support_status"] != "CONFIRMED"
    if mode == "no_Final_R":
        assert audit["raw_final"] is None
        assert chain["R_Final_support_status"] != "CONFIRMED"
    if valid:
        store = DurableStore(root / OUTPUT / "synthetic_export")
        index = export(
            root,
            store,
            [row],
            {row["label"]: session},
            {"session_class_ids": {row["label"]: "synthetic-class"}},
        )
        assert index["tokenizer_loaded"] is False
        assert index["valid_original_packages"] == 1
        package = index["packages"][0]
        candidate = read_json(
            store.root / (package["positive_responses"][0]["path_prefix"] + ".candidate.json")
        )
        assert candidate["input_messages"][0]["content"] == SYSTEMS_NEW[arm]
        assert candidate["target_response"] == raw[0]


def test_full_denominator_unknown_mapping_and_no_N_E_class_pooling(prototypes):
    rows, projections, chains = [], [], []
    for arm in ARMS:
        for task in TASKS:
            for rep in range(1, 9):
                label = f"{arm}_{task}_{rep:02d}"
                valid = rep <= 3
                row = record(
                    "synthetic_reviewed",
                    label=label,
                    arm=arm,
                    task_key=task,
                    formula_driven_trace_verified=valid,
                    answer={"V_quantity": "PASS" if valid else "UNDETERMINED", "V_format": "PASS"},
                    trace_status="PASS" if valid else "UNDETERMINED",
                )
                rows.append(row)
                if valid:
                    prototype = prototypes["tasks"][arm][task]["R"]
                    projections.append(
                        {
                            "session_label": label,
                            "population": arm,
                            "task_key": task,
                            "source_closeout_id": row["id"],
                            "status": "MAPPED" if rep <= 2 else "UNDETERMINED",
                            "behavior_signature": prototype["signature"] if rep <= 2 else None,
                            "behavior_key": prototype["behavior_key"] if rep <= 2 else None,
                        }
                    )
                chains.append(
                    {
                        "label": label,
                        "public_R_mention": {"status": "CONFIRMED" if rep <= 2 else "UNDETERMINED"},
                        "R_execution_status": "CONFIRMED" if rep <= 2 else "UNDETERMINED",
                        "R_source_relation_status": "PASS" if rep <= 2 else "UNDETERMINED",
                        "R_Final_support_status": "CONFIRMED" if rep <= 2 else "UNDETERMINED",
                        "complete_behavior_label": "PURE_R"
                        if rep <= 2
                        else "UNDETERMINED"
                        if valid
                        else "NOT_JOINT_VALID",
                    }
                )
    result = measure(rows, projections, chains)
    for arm in ARMS:
        for task in TASKS:
            row = result["populations"][arm]["tasks"][task]
            assert row["registered"] == 8 and row["valid_count"] == 3
            assert row["valid_pure_R_yield"] == "1/4"
            assert row["known_complete_classes"][0]["conditional_mass_over_all_valid"] == "2/3"
            assert row["mapping_unresolved_mass_over_valid"] == "1/3"
            assert not row["training_input_instantiated"]
    assert result["session_class_ids"]["N_X1_01"] != result["session_class_ids"]["E_X1_01"]


def test_full_class_cannot_be_reassigned_to_another_exploration_condition(prototypes):
    original = prototypes["tasks"]["E"]["X1"]["R"]
    projection = {
        "status": "MAPPED",
        "behavior_signature": original["signature"],
        "behavior_key": original["behavior_key"],
    }
    with pytest.raises(ValueError, match="same_registered_condition"):
        complete_class(projection, prototypes["tasks"]["N"]["X1"])
