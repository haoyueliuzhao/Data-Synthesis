from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

from .evaluation import (
    BenchmarkPrediction,
    benchmark_prediction_id,
    benchmark_snapshot_manifest_hash,
    load_benchmark_examples,
)
from .schema import (
    VTDO_EXPERIMENT_VERSION,
    ExternalBenchmarkSnapshot,
    VTDOTrainingRunResult,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BenchmarkGenerationConfig(FrozenModel):
    max_input_tokens: int = Field(default=16_384, ge=512)
    max_new_tokens: int = Field(default=256, ge=16, le=2_048)
    temperature: float = Field(default=0.0, ge=0)
    top_p: float = Field(default=1.0, gt=0, le=1)
    seed: int = 20260731
    device: str = "cuda:0"
    prompt_contract: str = "native_financial_answer_json.v2"

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="benchmark_generation_config:")


class BenchmarkTextGenerator(Protocol):
    generator_manifest_hash: str

    def generate(self, prompt: str, config: BenchmarkGenerationConfig) -> str: ...


class BenchmarkPredictionRunManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    prediction_run_id: str = Field(min_length=1)
    arm_id: str = Field(min_length=1)
    training_result_id: str = Field(min_length=1)
    training_result_path: str = Field(min_length=1)
    training_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    training_config_hash: str = Field(min_length=1)
    training_dataset_hash: str = Field(min_length=1)
    training_seed: int
    adapter_dir: str = Field(min_length=1)
    base_model_ref: str = Field(min_length=1)
    adapter_manifest_hash: str = Field(min_length=1)
    base_model_manifest_hash: str = Field(min_length=1)
    generator_manifest_hash: str = Field(min_length=1)
    generation_config_hash: str = Field(min_length=1)
    evaluation_snapshot_hash: str = Field(min_length=1)
    benchmark_ids: tuple[str, ...] = Field(min_length=1)
    benchmark_snapshot_count: int = Field(ge=1)
    prediction_count: int = Field(ge=0)
    contract_success_count: int = Field(ge=0)
    predictions_path: str = Field(min_length=1)
    predictions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: str
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> BenchmarkPredictionRunManifest:
        if self.schema_version != VTDO_EXPERIMENT_VERSION:
            raise ValueError("benchmark prediction manifest schema version is invalid")
        if self.status not in {"completed", "partial"}:
            raise ValueError("unknown benchmark prediction status")
        if self.contract_success_count > self.prediction_count:
            raise ValueError("benchmark contract-success count exceeds predictions")
        expected = (
            "completed" if self.contract_success_count == self.prediction_count else "partial"
        )
        if self.status != expected:
            raise ValueError("benchmark prediction status is inconsistent")
        if self.benchmark_snapshot_count != len(self.benchmark_ids):
            raise ValueError("benchmark snapshot identity count is inconsistent")
        if tuple(sorted(set(self.benchmark_ids))) != self.benchmark_ids:
            raise ValueError("benchmark IDs must be ordered and unique")
        if self.manifest_id != benchmark_prediction_run_manifest_id(self):
            raise ValueError("benchmark prediction manifest identity is invalid")
        return self


def run_benchmark_predictions(
    snapshots: tuple[ExternalBenchmarkSnapshot, ...],
    training_result_path: Path,
    generation_config: BenchmarkGenerationConfig,
    output_dir: Path,
    *,
    generator: BenchmarkTextGenerator | None = None,
) -> BenchmarkPredictionRunManifest:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"benchmark prediction output directory is not empty: {output_dir}")
    training_result = VTDOTrainingRunResult.model_validate_json(
        training_result_path.read_text(encoding="utf-8")
    )
    training_result_sha256 = _sha256(training_result_path)
    examples = load_benchmark_examples(snapshots)
    adapter_dir = Path(training_result.adapter_dir)
    if not adapter_dir.is_dir():
        raise ValueError(f"training adapter directory is missing: {adapter_dir}")
    adapter_hash = _directory_manifest_hash(adapter_dir, prefix="adapter_manifest:")
    base_path = Path(training_result.base_model)
    base_hash = (
        _directory_manifest_hash(base_path, prefix="base_model_manifest:")
        if base_path.is_dir()
        else canonical_hash(
            {
                "repository": training_result.base_model,
                "revision": training_result.model_revision,
            },
            prefix="remote_base_model_manifest:",
        )
    )
    if adapter_hash != training_result.adapter_manifest_hash:
        raise ValueError("training Adapter content differs from its frozen result")
    if base_hash != training_result.base_model_manifest_hash:
        raise ValueError("base model content differs from its frozen result")
    active_generator = generator or HuggingFaceBenchmarkGenerator(
        training_result,
        generation_config,
        adapter_hash=adapter_hash,
        base_model_hash=base_hash,
    )
    snapshot_hash = benchmark_snapshot_manifest_hash(snapshots)
    run_identity = {
        "arm_id": training_result.arm_id,
        "training_result_id": training_result.result_id,
        "training_result_path": str(training_result_path.resolve()),
        "training_result_sha256": training_result_sha256,
        "training_config_hash": training_result.config_hash,
        "training_dataset_hash": training_result.dataset_hash,
        "training_seed": training_result.training_seed,
        "adapter_dir": str(adapter_dir.resolve()),
        "base_model_ref": training_result.base_model,
        "adapter_manifest_hash": adapter_hash,
        "base_model_manifest_hash": base_hash,
        "generator_manifest_hash": active_generator.generator_manifest_hash,
        "generation_config_hash": generation_config.config_hash,
        "evaluation_snapshot_hash": snapshot_hash,
        "benchmark_ids": tuple(sorted(item.benchmark_id for item in snapshots)),
        "benchmark_snapshot_count": len(snapshots),
    }
    run_id = canonical_hash(run_identity, prefix="benchmark_prediction_run:")
    predictions: list[BenchmarkPrediction] = []
    for index, example in enumerate(examples):
        raw_response = active_generator.generate(
            example.prompt,
            generation_config.model_copy(update={"seed": generation_config.seed + index}),
        )
        answer, scale, program, contract_success = _parse_answer_contract(
            raw_response,
            require_program=example.benchmark_id == "finqa",
        )
        values = {
            "prediction_run_id": run_id,
            "benchmark_id": example.benchmark_id,
            "example_id": example.example_id,
            "answer": answer,
            "scale": scale,
            "program": program,
            "contract_success": contract_success,
            "raw_response_hash": canonical_hash(
                raw_response,
                prefix="benchmark_raw_response:",
            ),
        }
        provisional = BenchmarkPrediction.model_construct(prediction_id="pending", **values)
        predictions.append(
            BenchmarkPrediction(
                prediction_id=benchmark_prediction_id(provisional),
                **values,
            )
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = output_dir / "benchmark_predictions.jsonl"
    prediction_path.write_text(
        "".join(item.model_dump_json() + "\n" for item in predictions),
        encoding="utf-8",
    )
    manifest_values = {
        **run_identity,
        "prediction_run_id": run_id,
        "prediction_count": len(predictions),
        "contract_success_count": sum(item.contract_success for item in predictions),
        "predictions_path": str(prediction_path.resolve()),
        "predictions_sha256": _sha256(prediction_path),
        "status": (
            "completed" if all(item.contract_success for item in predictions) else "partial"
        ),
        "schema_version": VTDO_EXPERIMENT_VERSION,
    }
    provisional_manifest = BenchmarkPredictionRunManifest.model_construct(
        manifest_id="pending",
        **manifest_values,
    )
    manifest = BenchmarkPredictionRunManifest(
        manifest_id=benchmark_prediction_run_manifest_id(provisional_manifest),
        **manifest_values,
    )
    (output_dir / "benchmark_prediction_manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


class HuggingFaceBenchmarkGenerator:
    def __init__(
        self,
        training_result: VTDOTrainingRunResult,
        config: BenchmarkGenerationConfig,
        *,
        adapter_hash: str,
        base_model_hash: str,
    ) -> None:
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("benchmark inference dependencies are missing") from exc
        if config.device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("benchmark inference requested CUDA but CUDA is unavailable")
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(
            training_result.adapter_dir,
            use_fast=True,
            trust_remote_code=False,
        )
        base = AutoModelForCausalLM.from_pretrained(
            training_result.base_model,
            revision=training_result.model_revision,
            dtype=torch.bfloat16 if config.device.startswith("cuda") else torch.float32,
            trust_remote_code=False,
            use_safetensors=True,
        )
        self._model = PeftModel.from_pretrained(base, training_result.adapter_dir)
        self._model.to(config.device)
        self._model.eval()
        self._device = config.device
        self.generator_manifest_hash = canonical_hash(
            {
                "implementation": "huggingface_peft_benchmark_generator.v1",
                "training_result_id": training_result.result_id,
                "adapter_manifest_hash": adapter_hash,
                "base_model_manifest_hash": base_model_hash,
            },
            prefix="benchmark_generator_manifest:",
        )

    def generate(self, prompt: str, config: BenchmarkGenerationConfig) -> str:
        random.seed(config.seed)
        self._torch.manual_seed(config.seed)
        encoded = self._tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=config.max_input_tokens,
        ).to(self._device)
        with self._torch.inference_mode():
            generation_arguments = {
                "max_new_tokens": config.max_new_tokens,
                "do_sample": config.temperature > 0,
                "pad_token_id": self._tokenizer.eos_token_id,
            }
            if config.temperature > 0:
                generation_arguments.update(
                    {"temperature": config.temperature, "top_p": config.top_p}
                )
            generated = self._model.generate(**encoded, **generation_arguments)
        completion = generated[0, encoded["input_ids"].shape[1] :]
        return str(self._tokenizer.decode(completion, skip_special_tokens=True)).strip()


def benchmark_prediction_run_manifest_id(value: BenchmarkPredictionRunManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="benchmark_prediction_run_manifest:",
    )


def _parse_answer_contract(
    raw_response: str,
    *,
    require_program: bool,
) -> tuple[object, str, str, bool]:
    candidate = raw_response.strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if match is None:
            return candidate, "", "", False
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return candidate, "", "", False
    if not isinstance(payload, dict) or "answer" not in payload:
        return candidate, "", "", False
    scale = payload.get("scale", "")
    program = payload.get("program", "")
    if not isinstance(scale, str):
        return payload["answer"], "", "", False
    if not isinstance(program, str) or (require_program and not program.strip()):
        return payload["answer"], scale, "", False
    return payload["answer"], scale, program.strip(), True


def _directory_manifest_hash(path: Path, *, prefix: str) -> str:
    files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
    if not files:
        raise ValueError(f"model directory has no files: {path}")
    identity = {
        str(item.relative_to(path)): {
            "size": item.stat().st_size,
            "sha256": _sha256(item),
        }
        for item in files
    }
    return canonical_hash(identity, prefix=prefix)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
