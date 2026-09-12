"""CPU toy callbacks only: no real tokenizer, model weights, CUDA or Teacher."""

import copy
import json
import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_student import decoder, evaluation
from trusted_synthesis.experiments.finance_qa_vnext_basis_student.protocol import (
    BINDING_FIELDS,
    read_json,
    record,
    sha,
    training_config,
    write_once,
)
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import runtime


class ToyTokenizer:
    chat_template = "synthetic complete chat template"
    eos_token_id, pad_token_id, bos_token_id = 1, 0, None

    def __init__(self, length=12):
        self.length, self.calls, self.rendered_messages = length, [], []

    def apply_chat_template(self, messages, **options):
        assert options == {"tokenize": False, "add_generation_prompt": True}
        self.rendered_messages.append(copy.deepcopy(messages))
        return json.dumps(messages, ensure_ascii=False) + "GENERATION_START"

    def __call__(self, text, **options):
        assert options == {"add_special_tokens": False, "truncation": False, "padding": False}
        self.calls.append((text, options))
        return {"input_ids": [17] * self.length, "attention_mask": [1] * self.length}

    def decode(self, tokens, **options):
        assert options == {"skip_special_tokens": False, "clean_up_tokenization_spaces": False}
        return "".join(
            "<EOS1>" if token == 1 else "<EOS2>" if token == 2 else chr(token) for token in tokens
        )


class ToyModel:
    def __init__(self, generated=None, error=None):
        self.generated = (
            generated if generated is not None else [ord(char) for char in '{"final":{}}'] + [1]
        )
        self.error, self.calls, self.training, self.gradients = error, [], True, True

    def requires_grad_(self, enabled):
        self.gradients = enabled
        return self

    def eval(self):
        self.training = False
        return self

    def generate(self, **arguments):
        self.calls.append(copy.deepcopy(arguments))
        assert self.training is False and self.gradients is False
        if self.error:
            raise self.error
        return [arguments["input_ids"][0] + self.generated]


def assets():
    tokenizer = {
        "id": "synthetic-tokenizer",
        "chat_template": ToyTokenizer.chat_template,
        "chat_template_sha256": sha(ToyTokenizer.chat_template),
        "eos_token_id": 1,
        "pad_token_id": 0,
        "bos_token_id": None,
    }
    base = {
        "id": "synthetic-base",
        "config": {"max_position_embeddings": 32768},
        "generation_config": {"eos_token_id": [1, 2], "pad_token_id": 0, "bos_token_id": 9},
    }
    return tokenizer, base


def make_decoder(path, *, length=12, generated=None, error=None, pool="A"):
    tokenizer_binding, base_binding = assets()
    configuration = decoder.bind_policy(tokenizer_binding, base_binding)
    identity = record(
        "model_identity",
        **{
            key: "synthetic-" + key
            for key in BINDING_FIELDS
            if key not in {"training_config_id", "decoder_config_id"}
        },
        training_config_id=training_config()["id"],
        decoder_config_id=configuration["id"],
        pool=pool,
        arm="alpha0",
        seed=11,
        checkpoint_id="synthetic-parameter-digest",
        training_report_id="synthetic-only-report",
        base_binding_id=base_binding["id"],
        tokenizer_binding_id=tokenizer_binding["id"],
        adapter_directory="synthetic-adapters",
        final_adapter={
            "path": "final.safetensors",
            "bytes": 0,
            "sha256": "0" * 64,
            "parameter_digest": "synthetic-parameter-digest",
        },
    )
    load = record(
        "model_load_receipt",
        model_identity_id=identity["id"],
        execution_kind=decoder.CONTROL,
        restored_checkpoint_id=identity["checkpoint_id"],
        model_weight_loads=0,
        final_adapter_loads=0,
        tokenizer_loads=0,
        GPU_loads=0,
    )
    return decoder.BoundDecoder(
        ToyModel(generated, error),
        ToyTokenizer(length),
        tokenizer_binding,
        identity,
        path,
        base_binding=base_binding,
        configuration=configuration,
        execution_kind=decoder.CONTROL,
        load_receipt=load,
    )


def public_input(model_identity, task_id="toy-task", group="dual_sufficient"):
    sources = runtime.SnapshotSources.synthetic({"synthetic-public": {"facts": {}}})
    public = {
        "question": "An original public synthetic question; no private target exists.",
        "period_contract": {"task_id": task_id, "source_cluster": "cik:0000012345"},
        "source_document": sources.descriptors()[0],
        "quantity_contract": {},
        "source_policy": "original public source only",
        "tool_contract": {},
    }
    messages = [{"role": "user", "content": json.dumps(public)}]
    identity = {
        "task_id": task_id,
        "family": group,
        "surface_version_id": "synthetic-surface",
        "public_messages_sha256": runtime.sha(runtime.encode(messages)),
        "parent_manifest_id": model_identity["surface_manifest_id"],
    }
    context = {
        "identity": identity,
        "response_index": 0,
        "max_responses": 32,
        "max_tools": 32,
        "remaining_tool_calls": 32,
        "history_must_not_be_truncated": True,
    }
    runtime_messages = [
        {"role": "system", "content": runtime.SYSTEM + "\nRequested guidance: neutral"},
        *messages,
    ]
    return messages, identity, context, runtime_messages, sources


def test_actual_asset_ids_not_old_decoder_literals():
    tokens, base = assets()
    config = decoder.bind_policy(tokens, base)
    assert config["eos_token_ids"] == [1, 2] and config["bos_token_id"] == 9
    assert config["pad_token_id"] == 0 and config["policy"]["max_new_tokens"] == 2048
    assert config["policy"]["maximum_sequence_length"] == 24576


@pytest.mark.parametrize("length,allowed", [(22528, True), (22529, False), (24577, False)])
def test_full_context_reservation_and_no_model_call_when_insufficient(tmp_path, length, allowed):
    local = make_decoder(tmp_path / "decoder", length=length)
    _, _, context, messages, _ = public_input(local.identity)
    if allowed:
        result = local(messages, context)
        assert result["receipt"]["model_generation_invoked"]
    else:
        with pytest.raises(decoder.ContextRejected):
            local(messages, context)
        assert local.model.calls == []
        assert local.fatal_error is None
    assert len(local.receipts) == 1
    stored = read_json(tmp_path / "decoder/callback_000001/receipt.json")
    assert stored["prompt_token_count"] == length and not stored["prompt_truncated"]
    assert local.snapshot()["context_rejections"] == (not allowed)
    assert local.snapshot()["actual_GPU_generation_calls"] == 0


def test_raw_spaces_json_errors_and_only_actual_final_EOS_preserved(tmp_path):
    text = " \nnot valid JSON  \n"
    local = make_decoder(tmp_path / "decoder", generated=[ord(char) for char in text] + [1])
    _, _, context, messages, _ = public_input(local.identity)
    result = local(messages, context)
    assert set(result) == {"raw_response", "receipt"} and result["raw_response"] == text
    receipt = result["receipt"]
    assert receipt["raw_generated_text"] == text + "<EOS1>"
    assert receipt["generated_token_ids"][-1] == 1
    assert receipt["public_content_token_ids"] == [ord(char) for char in text]
    assert not receipt["host_JSON_repair"] and not receipt["automatic_continuation"]
    request = read_json(tmp_path / "decoder/callback_000001/request.json")
    assert request["input_messages"] == messages
    assert request["rendered_prompt"] == local.tokenizer.calls[0][0]
    assert local.model.calls[0]["max_new_tokens"] == 2048
    assert local.model.calls[0]["num_beams"] == 1
    assert local.model.calls[0]["repetition_penalty"] == 1


def test_interior_special_token_is_never_stripped(tmp_path):
    local = make_decoder(tmp_path / "decoder", generated=[65, 1, 66, 2])
    _, _, context, messages, _ = public_input(local.identity)
    assert local(messages, context)["raw_response"] == "A<EOS1>B"


@pytest.mark.parametrize(
    "generated,finish", [([], "model_stopped_without_EOS"), ([65] * 2048, "new_token_limit")]
)
def test_length_or_empty_original_return_is_not_repaired_or_continued(tmp_path, generated, finish):
    local = make_decoder(tmp_path / "decoder", generated=generated)
    _, _, context, messages, _ = public_input(local.identity)
    result = local(messages, context)
    assert result["receipt"]["finish_reason"] == finish and len(local.model.calls) == 1
    assert result["receipt"]["generated_token_ids"] == generated


def test_context_rejection_is_a_callback_but_not_an_assistant_response(tmp_path):
    local = make_decoder(tmp_path / "decoder", length=22529)
    messages, identity, _, _, sources = public_input(local.identity)
    session = runtime.generate(messages, identity, sources, provider=local)
    assert session["provider_calls"] == 1 and session["turns"] == []
    assert (
        session["terminal"] == "provider_error" and "ContextRejected" in session["provider_error"]
    )
    assert local.snapshot()["model_generate_api_calls"] == 0
    assert local.snapshot()["callback_attempts"] == 1


def test_generate_fault_has_persistent_receipt_and_prevents_later_callback(tmp_path):
    local = make_decoder(tmp_path / "decoder", error=RuntimeError("synthetic CUDA OOM"))
    _, _, context, messages, _ = public_input(local.identity)
    with pytest.raises(decoder.DecoderFailure, match="OOM"):
        local(messages, context)
    assert (tmp_path / "decoder/callback_000001/receipt.json").exists()
    assert (tmp_path / "decoder/callback_000001/failure.json").exists()
    assert local.snapshot()["model_generate_api_calls"] == 1
    assert local.snapshot()["completed_generation_calls"] == 0
    with pytest.raises(ValueError, match="no_callbacks_after"):
        local(messages, context)
    assert len(local.model.calls) == 1


@pytest.fixture
def public_panel(monkeypatch):
    # No private fixture or target is constructed anywhere in this fixture.
    groups = ["dual_sufficient", "composition_required", "other_financial"]
    monkeypatch.setattr(evaluation, "QUOTAS", {"dev": dict.fromkeys(groups, 1)})
    tasks = [{"task_id": "toy-" + group, "family": group, "split": "dev"} for group in groups]

    class PublicOnly:
        instances = 0

        def __init__(self, root, directory, expected):
            PublicOnly.instances += 1
            self.catalog = {"id": "synthetic-public-catalog", "tasks": tasks}
            self.expected = expected

        def public_envelope(self, task_id):
            row = next(row for row in tasks if row["task_id"] == task_id)
            messages, identity, _, _, _ = public_input(
                {"surface_manifest_id": self.expected}, task_id, row["family"]
            )
            return {"messages": messages, "identity": identity}

    monkeypatch.setattr(evaluation, "PublicOverlay", PublicOnly)
    from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import overlay

    def forbidden(*args, **kwargs):
        raise AssertionError("generation must never construct OfflineOverlay/private fixture")

    monkeypatch.setattr(overlay, "OfflineOverlay", forbidden)
    return PublicOnly


def run_public(tmp_path, public_panel, **options):
    local = make_decoder(tmp_path / "generation/decoder", **options)
    report = evaluation.generate(
        tmp_path,
        "generation",
        surface_directory="synthetic-surfaces",
        surface_manifest_id=local.identity["surface_manifest_id"],
        split="dev",
        model_identity=local.identity,
        decoder=local,
    )
    return local, report


def test_public_worker_never_opens_private_or_claims_actual_CPU_control(tmp_path, public_panel):
    local, report = run_public(tmp_path, public_panel)
    assert report["status"] == "SYNTHETIC_GENERATION_CONTROL" and not report["actual_complete"]
    assert report["completed_task_count"] == 3 and report["private_task_bundles_opened"] == 0
    assert report["resource_usage"]["model_generate_api_calls"] == 3
    assert report["resource_usage"]["actual_model_generation_calls"] == 0
    assert report["resource_usage"]["synthetic_model_generation_calls"] == 3
    assert report["resource_usage"]["tokenizer_loads"] == 0
    assert public_panel.instances == 1
    manifest = evaluation.verify_output(tmp_path / "generation")
    with pytest.raises(ValueError, match="only_complete_actual"):
        evaluation.score(
            tmp_path, "generation", "score", expected_generation_manifest_id=manifest["id"]
        )
    assert not (tmp_path / "score").exists()
    assert all(
        messages[0]["content"].endswith("Requested guidance: neutral")
        for messages in local.tokenizer.rendered_messages
    )


def test_hardware_fault_does_not_run_remaining_tasks_or_claim_complete(tmp_path, public_panel):
    local, report = run_public(tmp_path, public_panel, error=RuntimeError("synthetic OOM"))
    assert report["status"] == "INCOMPLETE_GENERATION" and report["actual_complete"] is False
    assert report["completed_task_count"] == 1 and len(local.model.calls) == 1
    assert (tmp_path / "generation/failure.json").exists()
    assert (tmp_path / "generation/sessions/toy-dual_sufficient/runtime_session.json").exists()
    evaluation.verify_output(tmp_path / "generation")


def test_expected_context_rejections_keep_whole_task_denominator(tmp_path, public_panel):
    local, report = run_public(tmp_path, public_panel, length=22529)
    assert report["complete_registered_denominator"] and report["completed_task_count"] == 3
    assert report["resource_usage"]["context_rejections"] == 3
    assert report["resource_usage"]["callback_attempts"] == 3 and not local.model.calls
    assert report["failure_id"] is None


def test_sealed_generation_no_overwrite_or_unpinned_reopen(tmp_path, public_panel):
    _, report = run_public(tmp_path, public_panel)
    with pytest.raises(ValueError, match="identity_pin"):
        evaluation.verify_output(tmp_path / "generation", "wrong-manifest")
    again = make_decoder(tmp_path / "generation/decoder")
    with pytest.raises(ValueError, match="no_reexecution"):
        evaluation.generate(
            tmp_path,
            "generation",
            surface_directory="synthetic-surfaces",
            surface_manifest_id=again.identity["surface_manifest_id"],
            split="dev",
            model_identity=again.identity,
            decoder=again,
        )
    assert read_json(tmp_path / "generation/report.json") == report


def test_bound_identity_contains_no_private_answer_or_material_payload(tmp_path):
    local = make_decoder(tmp_path / "decoder")
    body = {
        key: value for key, value in local.identity.items() if key not in {"id", "schema_version"}
    }
    body["private"] = {"answer": "must not be accepted"}
    with pytest.raises(ValueError, match="closed_fields"):
        decoder.validate_model_identity(record("model_identity", **body))


def changed_record(kind, value, **changes):
    return record(
        kind,
        **{
            **{key: item for key, item in value.items() if key not in {"id", "schema_version"}},
            **changes,
        },
    )


@pytest.fixture
def offline_evidence(tmp_path, public_panel, monkeypatch):
    """CPU-only simulated saved actual-format evidence, never a production output.

    The online part uses no private objects. Only the explicitly mocked offline
    capability below constructs its toy private reference when score calls it.
    """
    local, original_report = run_public(tmp_path, public_panel)
    directory = tmp_path / "generation"
    files = {
        str(path.relative_to(directory)): read_json(path) for path in directory.rglob("*.json")
    }
    load = changed_record(
        "model_load_receipt",
        files["model_load_receipt.json"],
        execution_kind=decoder.ACTUAL,
        model_weight_loads=1,
        final_adapter_loads=1,
        tokenizer_loads=1,
        GPU_loads=1,
    )
    files["model_load_receipt.json"] = load
    for reference in original_report["results"]:
        name = reference["result_path"]
        result = files[name]
        session_name = result["runtime_session_path"]
        session = copy.deepcopy(files[session_name])
        refs = []
        for pointer, turn in zip(result["decoder_receipts"], session["turns"], strict=True):
            receipt = changed_record(
                "decoder_receipt",
                files[pointer["path"]],
                execution_kind=decoder.ACTUAL,
                GPU_generation_invoked=True,
            )
            files[pointer["path"]] = receipt
            request_name = pointer["path"].replace("receipt.json", "request.json")
            files[request_name] = changed_record(
                "decoder_request", files[request_name], execution_kind=decoder.ACTUAL
            )
            turn["provider_receipt"] = receipt
            refs.append({**pointer, "id": receipt["id"]})
        session = runtime.record(
            "evaluation_session",
            **{key: value for key, value in session.items() if key not in {"id", "schema_version"}},
        )
        files[session_name] = session
        result = changed_record(
            "public_generation_result",
            result,
            runtime_session_id=session["id"],
            decoder_receipts=refs,
            execution_kind=decoder.ACTUAL,
        )
        files[name] = result
    usage = {
        **original_report["resource_usage"],
        "execution_kind": decoder.ACTUAL,
        "actual_model_generation_calls": 3,
        "synthetic_model_generation_calls": 0,
        "actual_GPU_generation_calls": 3,
        "model_weight_loads": 1,
        "final_adapter_loads": 1,
        "tokenizer_loads": 1,
        "GPU_model_loads": 1,
        "load_receipt_id": load["id"],
    }
    report = changed_record(
        "generation_report",
        original_report,
        status="COMPLETE_FIXED_GENERATION",
        actual_complete=True,
        execution_kind=decoder.ACTUAL,
        resource_usage=usage,
        results=[
            {**row, "result_id": files[row["result_path"]]["id"]}
            for row in original_report["results"]
        ],
    )
    files["report.json"] = report
    files["registration.json"] = changed_record(
        "generation_registration", files["registration.json"], process_id=os.getpid() + 1
    )
    original_read = evaluation.read_json

    def read_saved(path):
        path = Path(path)
        if path.is_relative_to(directory):
            return copy.deepcopy(files[str(path.relative_to(directory))])
        return original_read(path)

    monkeypatch.setattr(evaluation, "read_json", read_saved)
    monkeypatch.setattr(
        evaluation,
        "verify_output",
        lambda path, expected=None: {"id": "synthetic-manifest", "phase": "public_generation"},
    )
    private_calls = []
    from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import assessment
    from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import overlay

    class OfflineOnly:
        def __init__(self, root, surface, expected):
            self.public = public_panel(root, surface, expected)

        def fixture(self, task_id):
            private_calls.append(task_id)
            envelope = self.public.public_envelope(task_id)
            return {
                "identity": envelope["identity"],
                "bundle": {
                    "public": json.loads(envelope["messages"][0]["content"]),
                    "private": {"created_only_now_offline": True},
                },
                "native_bindings": {},
                "sources": None,
            }

    def assess_saved(session, bundle, bindings, sources):
        assert bundle["private"]["created_only_now_offline"]
        qualified = session["identity"]["family"] != "composition_required"
        return runtime.record(
            "evaluation_assessment",
            financial_valid=qualified,
            complete_trajectory_qualified=qualified,
            quantity_status="CORRECT" if qualified else "UNKNOWN",
            support_status="PASS" if qualified else "UNKNOWN",
            actual_method="UNDETERMINED",
            full_mapping_status="PENDING_REVIEW",
            reason=None if qualified else "no_proof",
        )

    monkeypatch.setattr(overlay, "OfflineOverlay", OfflineOnly)
    monkeypatch.setattr(assessment, "assess_session", assess_saved)
    return local, files, private_calls


def test_offline_score_receipt_join_preserves_full_denominator_and_actual_resources(
    tmp_path, offline_evidence
):
    _, _, private_calls = offline_evidence
    assert private_calls == []
    report = evaluation.score(
        tmp_path, "generation", "score", expected_generation_manifest_id="synthetic-manifest"
    )
    assert len(private_calls) == report["task_count"] == 3
    assert report["primary_utility"] == pytest.approx(2 / 3)
    assert [row["financial_valid"] for row in report["outcomes"]] == [True, False, True]
    assert all(row["full_mapping_status"] == "PENDING_REVIEW" for row in report["outcomes"])
    assert report["actual_model_resource_usage"]["model_weight_loads"] == 1
    assert report["actual_model_resource_usage"]["actual_GPU_generation_calls"] == 3
    assert report["scoring_GPU_calls"] == 0
    assert report["generation_process_id"] != report["scoring_process_id"]


@pytest.mark.parametrize(
    "mutation", ["legacy_zero_GPU", "mock_model_load", "same_process", "wrong_token_count"]
)
def test_offline_rejects_unproven_generation_before_private_open(
    tmp_path, offline_evidence, mutation
):
    _, files, private_calls = offline_evidence
    if mutation == "same_process":
        files["registration.json"] = changed_record(
            "generation_registration", files["registration.json"], process_id=os.getpid()
        )
    elif mutation == "mock_model_load":
        files["model_load_receipt.json"] = changed_record(
            "model_load_receipt", files["model_load_receipt.json"], execution_kind=decoder.CONTROL
        )
    else:
        usage = dict(files["report.json"]["resource_usage"])
        usage[
            "actual_GPU_generation_calls" if mutation == "legacy_zero_GPU" else "generated_tokens"
        ] = 0
        files["report.json"] = changed_record(
            "generation_report", files["report.json"], resource_usage=usage
        )
    with pytest.raises(ValueError):
        evaluation.score(
            tmp_path, "generation", "score", expected_generation_manifest_id="synthetic-manifest"
        )
    assert private_calls == []


def test_bad_JSON_and_feedback_remain_in_later_runtime_history(tmp_path):
    local = make_decoder(tmp_path / "decoder", generated=[ord(char) for char in "not JSON"] + [1])
    messages, identity, _, _, sources = public_input(local.identity)
    previous = local.model.generate

    def next_response(**kwargs):
        if local.model.calls:
            local.model.generated = [ord(char) for char in '{"final":{}}'] + [1]
        return previous(**kwargs)

    local.model.generate = next_response
    session = runtime.generate(messages, identity, sources, provider=local)
    assert session["provider_calls"] == 2 and len(local.model.calls) == 2
    assert session["turns"][0]["raw_response"] == "not JSON"
    second = session["turns"][1]["input_messages"]
    assert second[-2] == {"role": "assistant", "content": "not JSON"}
    assert "protocol_error" in json.loads(second[-1]["content"])
    assert local.tokenizer.rendered_messages[1] == second


def test_production_loader_mock_failure_keeps_attempt_and_partial_usage_unknown(
    tmp_path, monkeypatch
):
    from trusted_synthesis.experiments.finance_qa_vnext_basis_student import train

    local = make_decoder(tmp_path / "not-used")
    tokens, base = assets()
    adapter_path = tmp_path / "synthetic-adapters/final.safetensors"
    write_once(adapter_path, {"synthetic_only_not_actual_safetensors": True})
    adapter = {
        **local.identity["final_adapter"],
        "bytes": adapter_path.stat().st_size,
        "sha256": sha(adapter_path),
    }
    identity = changed_record("model_identity", local.identity, final_adapter=adapter)
    calls = []

    def fail_before_actual_load(*args, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("synthetic loader failure; no actual CUDA operation")

    monkeypatch.setattr(train, "load_registered_student", fail_before_actual_load)
    with pytest.raises(RuntimeError, match="synthetic loader"):
        decoder.load_decoder(
            tmp_path, tmp_path / "failed/decoder", identity, base, tokens, local.configuration
        )
    assert len(calls) == 1 and calls[0]["trainable"] is False
    failure = read_json(tmp_path / "failed/decoder/load_failure.json")
    assert failure["attempted_load_counts"] == {
        "model_load_attempts": 1,
        "tokenizer_load_attempts": 0,
    }
    assert failure["completed_load_counts"]["model_weight_loads"] == 0
    assert failure["partial_model_load_resource_usage_may_be_unknown"] is True
    assert failure["actual_complete"] is False and failure["automatic_retry"] is False


def test_non_neutral_guidance_never_reaches_model(tmp_path):
    local = make_decoder(tmp_path / "decoder")
    _, _, context, messages, _ = public_input(local.identity)
    messages[0]["content"] = messages[0]["content"].replace(
        "Requested guidance: neutral", "Requested guidance: movement"
    )
    with pytest.raises(decoder.DecoderFailure, match="original_public_messages"):
        local(messages, context)
    assert local.model.calls == []


def test_detokenization_fault_cannot_erase_already_generated_tokens(tmp_path):
    local = make_decoder(tmp_path / "decoder", generated=[65, 66, 1])
    _, _, context, messages, _ = public_input(local.identity)

    def fail_decode(*args, **kwargs):
        raise RuntimeError("synthetic decode failure after model already returned")

    local.tokenizer.decode = fail_decode
    with pytest.raises(decoder.DecoderFailure, match="decode failure"):
        local(messages, context)
    receipt = read_json(tmp_path / "decoder/callback_000001/receipt.json")
    assert receipt["model_generation_completed"] is True
    assert receipt["generated_token_ids"] == [65, 66, 1]
    assert receipt["generated_token_count"] == local.snapshot()["generated_tokens"] == 3
    assert local.snapshot()["completed_generation_calls"] == 1
    assert local.fatal_error is not None
