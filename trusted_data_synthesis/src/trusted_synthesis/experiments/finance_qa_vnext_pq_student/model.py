"""Local checkpoint binding and explicit, small low-rank adapters.

This module loads no model at import. Base checkpoint tensors are never updated;
only newly registered q_proj/v_proj A/B parameters receive optimizer gradients.
"""

import hashlib
import math
import random
from importlib.metadata import version

import torch
import torch.nn.functional as F
from safetensors import safe_open
from safetensors.torch import load_file, save_file
from torch import nn

from .plan import MODEL_DIRECTORY, MODEL_REVISION, read_json, record, require, training_config


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bind_checkpoint():
    require(not torch.cuda.is_initialized(), "model.binding_before_GPU_Student")
    directory = MODEL_DIRECTORY
    index = read_json(directory / "model.safetensors.index.json")
    config = read_json(directory / "config.json")
    require(
        config["model_type"] == "qwen2" and config["max_position_embeddings"] == 32768,
        "model.fixed_architecture",
    )
    names = sorted(set(index["weight_map"].values()))
    require(
        names == [f"model-{i:05d}-of-00004.safetensors" for i in range(1, 5)],
        "model.four_original_shards",
    )
    members = []
    tensor_shapes = {}
    for name in ["config.json", "generation_config.json", "model.safetensors.index.json", *names]:
        path = directory / name
        require(path.is_file() and not path.is_symlink(), "model.original_regular_file")
        members.append({"path": name, "bytes": path.stat().st_size, "sha256": file_digest(path)})
        if name in names:
            with safe_open(path, framework="pt", device="cpu") as archive:
                for key in archive.keys():
                    require(
                        key not in tensor_shapes and index["weight_map"][key] == name,
                        "model.tensor_shard_index",
                    )
                    tensor_shapes[key] = archive.get_slice(key).get_shape()
    require(set(tensor_shapes) == set(index["weight_map"]), "model.complete_tensor_index")
    return record(
        "student_checkpoint_binding",
        directory=str(directory),
        revision=MODEL_REVISION,
        members=members,
        config=config,
        generation_config=read_json(directory / "generation_config.json"),
        tensor_shapes=tensor_shapes,
        parameter_count=sum(math.prod(shape) for shape in tensor_shapes.values()),
        software={
            name: version(name) for name in ("torch", "transformers", "safetensors", "tokenizers")
        },
        exact_local_shards_bound=True,
        weights_loaded_as_Student=False,
        GPU_initialized=False,
        no_download=True,
        model_revision_directory_name_is_not_the_only_identity=True,
    )


def verify_checkpoint(binding):
    require(
        binding["directory"] == str(MODEL_DIRECTORY) and binding["revision"] == MODEL_REVISION,
        "model.checkpoint_location",
    )
    for member in binding["members"]:
        path = MODEL_DIRECTORY / member["path"]
        require(
            path.is_file()
            and not path.is_symlink()
            and path.stat().st_size == member["bytes"]
            and file_digest(path) == member["sha256"],
            "model.bound_checkpoint_bytes",
        )
    require(
        binding["software"] == {name: version(name) for name in binding["software"]},
        "model.bound_software",
    )


def configure_randomness(seed):
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(2)


class LowRankLinear(nn.Module):
    def __init__(self, original, rank, alpha, dropout):
        super().__init__()
        require(isinstance(original, nn.Linear), "adapter.linear_target")
        self.base = original
        self.base.requires_grad_(False)
        self.scaling = alpha / rank
        self.dropout = nn.Dropout(dropout)
        self.lora_A = nn.Parameter(
            torch.empty(
                rank, original.in_features, dtype=torch.float32, device=original.weight.device
            )
        )
        self.lora_B = nn.Parameter(
            torch.zeros(
                original.out_features, rank, dtype=torch.float32, device=original.weight.device
            )
        )
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))

    def forward(self, inputs):
        base = self.base(inputs)
        hidden = F.linear(self.dropout(inputs).float(), self.lora_A)
        delta = F.linear(hidden, self.lora_B) * self.scaling
        return base + delta.to(base.dtype)


def install_adapters(model, config=None):
    config = training_config() if config is None else config
    model.requires_grad_(False)
    targets = [
        (name, module)
        for name, module in model.named_modules()
        if isinstance(module, nn.Linear) and name.rsplit(".", 1)[-1] in config["target_modules"]
    ]
    require(bool(targets), "adapter.targets_present")
    for name, original in targets:
        parent_name, attribute = name.rsplit(".", 1)
        parent = model.get_submodule(parent_name)
        setattr(
            parent,
            attribute,
            LowRankLinear(
                original, config["lora_rank"], config["lora_alpha"], config["lora_dropout"]
            ),
        )
    parameters = {
        name: parameter for name, parameter in model.named_parameters() if parameter.requires_grad
    }
    require(
        all(
            name.endswith((".lora_A", ".lora_B")) and parameter.dtype == torch.float32
            for name, parameter in parameters.items()
        ),
        "adapter.only_declared_trainables",
    )
    return record(
        "trainable_adapter_scope",
        target_module_names=[name for name, _ in targets],
        trainable_shapes={name: list(parameter.shape) for name, parameter in parameters.items()},
        trainable_parameter_count=sum(parameter.numel() for parameter in parameters.values()),
        base_weights_frozen=True,
        input_output_embeddings_frozen=True,
        implementation=(
            "base(x)+(alpha/rank)*B(A(dropout(x))); A/B fp32, residual cast to base dtype"
        ),
    )


def adapter_tensors(model):
    return {
        name: parameter.detach().cpu().contiguous()
        for name, parameter in model.named_parameters()
        if name.endswith((".lora_A", ".lora_B"))
    }


def adapter_digest(model):
    digest = hashlib.sha256()
    for name, tensor in sorted(adapter_tensors(model).items()):
        digest.update(name.encode())
        digest.update(str(list(tensor.shape)).encode())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def save_adapter(model, path):
    require(not path.exists(), "adapter.no_checkpoint_overwrite")
    save_file(adapter_tensors(model), path)
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": file_digest(path),
        "parameter_digest": adapter_digest(model),
    }


def load_adapter(model, path, expected):
    require(
        path.stat().st_size == expected["bytes"] and file_digest(path) == expected["sha256"],
        "adapter.checkpoint_bytes",
    )
    state = load_file(path, device="cpu")
    actual = {
        name: parameter
        for name, parameter in model.named_parameters()
        if name.endswith((".lora_A", ".lora_B"))
    }
    require(set(actual) == set(state), "adapter.complete_parameter_set")
    with torch.no_grad():
        for name, parameter in actual.items():
            require(
                list(parameter.shape) == list(state[name].shape)
                and state[name].dtype == torch.float32,
                "adapter.shape_and_dtype",
            )
            parameter.copy_(state[name].to(parameter.device))
    require(
        adapter_digest(model) == expected["parameter_digest"], "adapter.restored_parameter_identity"
    )


def load_student(binding, seed, *, trainable, adapter_path=None, adapter_record=None):
    from transformers import AutoModelForCausalLM

    verify_checkpoint(binding)
    require(torch.cuda.is_available(), "model.cuda_required")
    configure_randomness(seed)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIRECTORY,
        dtype=torch.bfloat16,
        device_map={"": "cuda:0"},
        attn_implementation="sdpa",
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        token=False,
    )
    actual = {name: parameter for name, parameter in model.named_parameters()}
    require(set(actual) == set(binding["tensor_shapes"]), "model.exact_base_parameter_set")
    require(
        all(
            list(parameter.shape) == binding["tensor_shapes"][name]
            and parameter.dtype == torch.bfloat16
            and parameter.device.type == "cuda"
            for name, parameter in actual.items()
        ),
        "model.actual_loaded_shapes_dtype_device",
    )
    scope = None
    if trainable or adapter_path is not None:
        scope = install_adapters(model)
        require(
            len(scope["target_module_names"]) == 2 * model.config.num_hidden_layers,
            "model.all_q_v_layers",
        )
        if adapter_path is not None:
            require(adapter_record is not None, "adapter.binding_required")
            load_adapter(model, adapter_path, adapter_record)
    if trainable:
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.train()
    else:
        model.requires_grad_(False)
        model.eval()
        model.config.use_cache = True
    return model, scope
