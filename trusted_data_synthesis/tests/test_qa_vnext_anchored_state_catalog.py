"""Finite semantic-state controls; toy originals only, no live study or model assets."""

import copy
import itertools

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import state_catalog as states
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.protocol import (
    encode,
    record,
    sha,
    write_once,
)
from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation import design
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import worker
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import (
    materials,
    training_runtime,
)


def semantic_graph():
    return {
        "label": {"actual_method": "endpoint"},
        "nodes": [
            {
                "id": "earlier",
                "label": {"source": "source-A", "period": ["2020-01-01", "2020-12-31"]},
            },
            {
                "id": "later",
                "label": {"source": "source-B", "period": ["2021-01-01", "2021-12-31"]},
            },
            {"id": "delta", "label": {"operator": "subtract"}},
            {"id": "Final", "label": {"kind": "Final"}},
        ],
        "edges": [
            {"from": "earlier", "to": "delta", "role": "previous"},
            {"from": "later", "to": "delta", "role": "current"},
            {"from": "delta", "to": "Final", "role": "Final_support"},
        ],
    }


def rename(graph, mapping):
    graph = copy.deepcopy(graph)
    for node in graph["nodes"]:
        node["id"] = mapping[node["id"]]
    for edge in graph["edges"]:
        edge["from"], edge["to"] = mapping[edge["from"]], mapping[edge["to"]]
    return graph


def test_exact_DAG_invariant_to_reference_ids_and_independent_node_array_order():
    graph = semantic_graph()
    before = states.canonicalize_dag(graph)
    assert before["exact"]
    for ordering in itertools.permutations(graph["nodes"]):
        candidate = {**graph, "nodes": list(ordering), "edges": list(reversed(graph["edges"]))}
        candidate = rename(candidate, {"earlier": "X", "later": "Y", "delta": "Z", "Final": "F"})
        assert states.canonicalize_dag(candidate)["state_id"] == before["state_id"]


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "period",
        "subtract_role",
        "visibility",
        "revision",
        "verification",
        "Final",
        "actual_method",
    ],
)
def test_semantic_relations_are_not_merged_despite_same_numeric_answer(mutation):
    graph, changed = semantic_graph(), semantic_graph()
    if mutation == "source":
        changed["nodes"][0]["label"]["source"] = "different-original-source"
    elif mutation == "period":
        changed["nodes"][0]["label"]["period"] = ["2019-01-01", "2019-12-31"]
    elif mutation == "subtract_role":
        changed["edges"][0]["role"], changed["edges"][1]["role"] = "current", "previous"
    elif mutation == "Final":
        changed["edges"][-1]["from"] = "later"
    elif mutation == "actual_method":
        changed["label"]["actual_method"] = "movement"
    else:
        changed["edges"].append({"from": "earlier", "to": "later", "role": mutation})
    assert not states.isomorphic(graph, changed)


def test_cyclic_and_search_unproven_graphs_fail_instead_of_hash_merging():
    graph = semantic_graph()
    graph["edges"].append({"from": "Final", "to": "earlier", "role": "invalid_cycle"})
    with pytest.raises(ValueError, match="cycle"):
        states.canonicalize_dag(graph)
    symmetric = {
        "label": {},
        "nodes": [{"id": str(i), "label": {"same": True}} for i in range(6)],
        "edges": [],
    }
    with pytest.raises(states.CanonicalizationLimit):
        states.canonicalize_dag(symmetric, max_search_nodes=1)
    smaller = {**symmetric, "nodes": symmetric["nodes"][:3]}
    assert states.canonicalize_dag(smaller)["exact"]


def toy_original(
    task_id="toy-task",
    family="annual_flow",
    method="endpoint",
    *,
    variant=0,
    registered="toy-session",
    pool="A",
    mode=None,
):
    sources = [
        {
            "source_id": key,
            "unit": "USD",
            "raw_sha256": key + "-raw-sha",
            "original_url": "https://example.invalid/" + key,
            "native_pointer": "/" + key,
            "record": {"val": value, "start": start, "end": end, "accn": "original-accession"},
            "definition": "same complete original financial definition",
        }
        for key, value, start, end in [
            ("previous", 5, "2020-01-01", "2020-12-31"),
            ("current", 10, "2021-01-01", "2021-12-31"),
        ]
    ]
    public = {
        "question": "Synthetic signed current minus previous, in USD.",
        "sources": sources,
        "quantity_contract": {},
        "source_policy": "original",
        "tool_contract": {},
    }
    messages = [{"role": "user", "content": encode(public).decode()}]
    identity = {
        "task_id": task_id,
        "family": family,
        "surface_version_id": "toy-surface",
        "public_messages_sha256": sha(encode(messages)),
        "parent_manifest_id": "toy-parent",
    }
    actions = [
        {"tool": "read_source", "arguments": {"source_id": "previous", "unit": "USD"}},
        {"tool": "read_source", "arguments": {"source_id": "current", "unit": "USD"}},
        {
            "tool": "calculate",
            "arguments": {
                "expression": "current-previous" if variant == 0 else "current+(-previous)",
                "variables": {
                    "current": {"result_id": "tool:2"},
                    "previous": {"result_id": "tool:1"},
                },
                "unit": "USD",
            },
        },
        {"final": {"value": "5", "unit": "USD", "result_id": "tool:3"}},
    ]
    if mode in {"revision", "verification"}:
        extra = copy.deepcopy(actions[2])
        if mode == "revision":
            actions[2]["arguments"]["expression"] = "current+previous"
            extra["arguments"]["revises_result_id"] = "tool:3"
            actions[-1]["final"]["result_id"] = "tool:4"
        actions.insert(3, extra)
    if mode == "free_declaration":
        actions[-1]["unproved_declaration"] = "these calculations were independent"
    session = training_runtime.generate(
        messages,
        identity,
        provider=lambda _, context: encode(actions[context["response_index"]]).decode(),
        session_id=registered,
        requested_basis="control" if method == "control" else "neutral",
    )
    tools = [event["tool_call"] for event in session["events"] if event["tool_call"]]
    signature = worker.record(
        "finite_complete_signature",
        task_id=task_id,
        actual_method=method,
        events=[
            {
                "result_id": tool["call_id"],
                "kind": tool["tool"],
                "role": "explicitly_revised_calculation"
                if mode == "revision" and tool["call_id"] == "tool:3"
                else "redundant_target_recomputation"
                if mode == "verification" and tool["call_id"] == "tool:4"
                else "final_support",
                "unit": tool["result"]["unit"],
                "used_result_ids": tool["result"]["used_result_ids"],
                "source_locator": tool["result"].get("source_locator"),
            }
            for tool in tools
        ],
        first_final_result_id=actions[-1]["final"]["result_id"],
        target_cross_checks=[
            {
                "result_id": "tool:4",
                "first_final_result_id": "tool:3",
                "kind": "redundant_target_recomputation",
            }
        ]
        if mode == "verification"
        else [],
        revision_edges=[
            {
                "from_result_id": "tool:3",
                "to_result_id": "tool:4",
                "substantive_program_change": True,
                "revised_result_supports_first_final": True,
            }
        ]
        if mode == "revision"
        else [],
        shared_endpoint_base=False,
    )
    qualification = training_runtime.record(
        "training_assessment",
        session_id=session["id"],
        origin="live_teacher_callback",
        financial_valid=True,
        representation_eligible=True,
        authentic_Teacher_origin_verified=True,
        full_mapping_status="MAPPED",
        actual_method=method,
        full_class=signature["id"],
        full_signature=signature,
    )
    registered_row = {"session_id": registered, "task_id": task_id, "pool": pool}
    raw = materials.raw_package(session, qualification, registered_row)
    rows = [
        {
            "candidate_id": candidate["id"],
            "representation": {
                "input_ids": [1, 2 + variant + int(method == "movement"), 3, 4],
                "attention_mask": [1] * 4,
                "target_mask": [0, 1, 1, 0],
                "labels": [-100, 2 + variant + int(method == "movement"), 3, -100],
                "sequence_length": 4,
                "target_token_count": 2,
            },
        }
        for candidate in raw["candidates"]
    ]
    encoded = training_runtime.record(
        "encoded_original_package",
        raw_package_id=raw["id"],
        registered_session_id=registered,
        task_id=task_id,
        pool=pool,
        group=raw["group"],
        actual_method=method,
        full_class=signature["id"],
        rows=rows,
        consumable=True,
        errors=[],
        maximum_sequence_length=24576,
        tokenizer_binding_id="toy-tokenizer",
        whole_package_target_tokens=sum(
            row["representation"]["target_token_count"] for row in rows
        ),
        original_request_response_bytes_retained=True,
        truncation=False,
    )
    return {
        "session": session,
        "qualification": qualification,
        "raw_package": raw,
        "encoded_package": encoded,
    }


def test_structured_original_projection_is_real_replay_and_retains_old_signature():
    original = toy_original()
    snapshot = copy.deepcopy(original)
    mapping = states.project_session(original["session"], original["qualification"])
    assert mapping["status"] == "MAPPED", mapping
    assert original == snapshot
    assert mapping["original_signature_id"] == original["qualification"]["full_class"]
    roles = [edge["role"] for edge in mapping["semantic_DAG"]["edges"]]
    assert "input:current" in roles and "input:previous" in roles
    assert "Final_support" in roles and "observed_before_decision" in roles
    assert "2020-01-01" in encode(mapping["canonical_graph"]).decode()


def test_missing_or_tampered_original_evidence_never_forces_projection():
    original = toy_original()
    original["session"]["turns"][0]["raw_response"] = "free text that claims independence"
    mapping = states.project_session(original["session"], original["qualification"])
    assert mapping["status"] == "PENDING_REVIEW" and mapping["state_id"] is None


@pytest.mark.parametrize(
    "mode,edge_role",
    [
        ("revision", "explicit_revision"),
        ("verification", "inherited_check:redundant_target_recomputation"),
    ],
)
def test_actual_structured_revision_and_verification_are_preserved(mode, edge_role):
    original = toy_original(mode=mode)
    mapping = states.project_session(original["session"], original["qualification"])
    assert mapping["status"] == "MAPPED", mapping
    assert edge_role in [edge["role"] for edge in mapping["semantic_DAG"]["edges"]]
    plain = toy_original()
    assert (
        mapping["state_id"]
        != states.project_session(plain["session"], plain["qualification"])["state_id"]
    )


def test_genuine_free_declaration_not_a_tampered_hash_remains_pending():
    original = toy_original(mode="free_declaration")
    mapping = states.project_session(original["session"], original["qualification"])
    assert mapping["status"] == "PENDING_REVIEW"
    assert mapping["reasons"] == ["mapper.closed_structured_Final_only"]


@pytest.fixture(scope="module")
def toy_materials(tmp_path_factory):
    root = tmp_path_factory.mktemp("anchored-synthetic-originals")
    tasks = [{"task_id": group, "group": group} for group in design.DUAL_GROUPS]
    tasks += [{"task_id": "c0", "group": "control"}, {"task_id": "c1", "group": "control"}]
    family = {group: name for name, group in worker.FAMILY_TO_SCALE_GROUP.items()}
    descriptors, evidence = [], {}
    for task in tasks:
        for pool in ("A", "B"):
            for method in ("control",) if task["group"] == "control" else design.METHODS:
                for index in range(10):
                    session_id = f"{task['task_id']}-{pool}-{method}-{index}"
                    original = toy_original(
                        task["task_id"],
                        family[task["group"]],
                        method,
                        variant=index % 2,
                        registered=session_id,
                        pool=pool,
                    )
                    encoded = original["encoded_package"]
                    path = f"originals/{session_id}/encoded_package.json"
                    write_once(root / path, encoded)
                    descriptor = {
                        key: encoded[key]
                        for key in (
                            "registered_session_id",
                            "task_id",
                            "pool",
                            "group",
                            "actual_method",
                            "consumable",
                            "whole_package_target_tokens",
                        )
                    }
                    descriptor.update(
                        id=encoded["id"],
                        path=path,
                        sha256=sha(encode(encoded)),
                        role="train" if index < 8 else "heldout",
                        within_stratum_index=index,
                    )
                    descriptors.append(descriptor)
                    evidence[encoded["id"]] = original
    manifest = training_runtime.record(
        "fixed_AB_material_manifest",
        status="FIXED_AB_MATERIALS_READY",
        collection_complete=True,
        population_selection={"selected": tasks},
        packages=descriptors,
        tokenizer_binding={"id": "toy-tokenizer"},
    )
    catalog = states.build_catalog(manifest, evidence)
    assert catalog["status"] == "READY_STATE_TRAIN_SUPPORT", [
        row for row in catalog["package_mappings"] if row["status"] != "MAPPED"
    ][:1]
    return root, manifest, evidence, catalog, {"tasks": tasks}


def test_catalog_keeps_every_original_package_and_method_pushforward(toy_materials):
    _, manifest, _, catalog, _ = toy_materials
    states.validate_catalog(catalog, manifest)
    assert catalog["original_package_count"] == len(manifest["packages"]) == 160
    for support in catalog["task_support"]:
        assert sum(state["n_train"] for state in support["states"]) == (
            8 if support["group"] == "control" else 16
        )
        assert all(state["pi0"] == state["r"] for state in support["states"])
        assert len(support["states"]) == (2 if support["group"] == "control" else 4)


@pytest.mark.parametrize("role,ready", [("train", False), ("heldout", True)])
def test_missing_mapping_retained_with_separate_train_and_heldout_gates(toy_materials, role, ready):
    _, manifest, originals, _, _ = toy_materials
    absent = next(row for row in manifest["packages"] if row["role"] == role)
    evidence = {key: value for key, value in originals.items() if key != absent["id"]}
    catalog = states.build_catalog(manifest, evidence)
    assert len(catalog["package_mappings"]) == len(manifest["packages"])
    assert (catalog["status"] == "READY_STATE_TRAIN_SUPPORT") is ready
    if ready:
        states.validate_catalog(catalog, manifest)
    else:
        with pytest.raises(ValueError, match="every_original_training"):
            states.validate_catalog(catalog, manifest)


def test_deleting_unmapped_original_cannot_restore_ready(toy_materials):
    _, manifest, evidence, _, _ = toy_materials
    fields = {
        key: copy.deepcopy(value)
        for key, value in manifest.items()
        if key not in {"id", "schema_version"}
    }
    fields["packages"].pop(0)
    altered = training_runtime.record("fixed_AB_material_manifest", **fields)
    with pytest.raises(ValueError, match="eight_plus_two"):
        states.build_catalog(
            altered,
            {
                key: value
                for key, value in evidence.items()
                if key in {row["id"] for row in altered["packages"]}
            },
        )


def test_rehashed_state_count_or_method_cannot_override_originals(toy_materials):
    _, manifest, _, catalog, _ = toy_materials
    changed = {
        key: copy.deepcopy(value)
        for key, value in catalog.items()
        if key not in {"id", "schema_version"}
    }
    changed["task_support"][0]["states"][0]["n_train"] += 1
    with pytest.raises(ValueError, match="initial_pushforward"):
        states.validate_catalog(record("behavior_state_catalog", **changed), manifest)


def toy_parents(toy_materials, *, complete=True, missing_heldout=False):
    root, original_manifest, originals, _, _ = toy_materials
    collection_report = training_runtime.record(
        "fixed_collection_report",
        status="COMPLETE_FIXED_COLLECTION" if complete else "COLLECTION_RUNNING",
        collection_complete=complete,
        registered_session_count=24640,
    )
    manifest = training_runtime.record(
        "fixed_AB_material_manifest",
        **{
            **{
                key: value
                for key, value in original_manifest.items()
                if key not in {"id", "schema_version"}
            },
            "collection_id": collection_report["id"],
            "all_original_registered_denominators": 24640,
        },
    )
    physical = {"material_manifest.json": manifest}
    collection = {"report.json": collection_report}
    for descriptor in manifest["packages"]:
        original = originals[descriptor["id"]]
        session_id = descriptor["registered_session_id"]
        physical[session_id + "/encoded_package.json"] = original["encoded_package"]
        physical[session_id + "/raw_package.json"] = original["raw_package"]
        collection["sessions/" + session_id + "/session.json"] = original["session"]
        collection["sessions/" + session_id + "/qualification.json"] = original["qualification"]
    if missing_heldout:
        item = next(row for row in manifest["packages"] if row["role"] == "heldout")
        del physical[item["registered_session_id"] + "/raw_package.json"]

    class SyntheticPinnedParent:
        def __init__(self, relative, values):
            self.relative, self.directory, self.values = relative, root / relative, values
            self.members = {
                name: {"path": name, "sha256": sha(encode(value)), "bytes": len(encode(value))}
                for name, value in values.items()
            }
            self.manifest = {"id": "synthetic-only-parent:" + sha(encode(self.members))}
            self.reads, self.checked = [], False

        def read(self, member):
            self.reads.append(member)
            value = self.values[member]
            assert sha(encode(value)) == self.members[member]["sha256"]
            return copy.deepcopy(value)

        def check_manifest(self):
            self.checked = True

    return (
        root,
        SyntheticPinnedParent("originals", physical),
        SyntheticPinnedParent("collection", collection),
    )


def test_explicit_parent_loader_reads_all_original_eight_plus_two_and_evidence(toy_materials):
    root, material, collection = toy_parents(toy_materials)
    catalog = states.build_from_parents(root, material, collection)
    assert catalog["status"] == "READY_STATE_TRAIN_SUPPORT"
    assert len(material.reads) == len(collection.reads) == 321
    assert all(len(row["original_file_references"]) == 4 for row in catalog["package_mappings"])
    assert material.checked and collection.checked


def test_live_collection_or_missing_heldout_original_is_not_state_mapping_uncertainty(
    toy_materials,
):
    root, material, collection = toy_parents(toy_materials, complete=False)
    with pytest.raises(ValueError, match="closed_original_collection"):
        states.build_from_parents(root, material, collection)
    root, material, collection = toy_parents(toy_materials, missing_heldout=True)
    with pytest.raises(KeyError):
        states.build_from_parents(root, material, collection)
