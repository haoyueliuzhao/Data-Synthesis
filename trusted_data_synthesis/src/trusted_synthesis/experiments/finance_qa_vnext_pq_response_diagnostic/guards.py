"""Instrumented phase separation and immutable inference, not OS isolation proof."""

import builtins
import hashlib
import io
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from trusted_synthesis.experiments.finance_qa_vnext_pq_student.guards import offline_guard

from .plan import OUTPUT, PARENT, SOURCE, encode, record, require


@contextmanager
def artifact_guard(root, phase, variant):
    """Default-deny artifact reads except each worker's predeclared inputs/outputs."""
    root = Path(root).resolve()
    artifact_root = root / "trusted_data_synthesis/artifacts"
    prep = root / OUTPUT / "preparation"
    allowed_files = {
        prep / name
        for name in (
            "configuration.json",
            "models.json",
            "checkpoint_binding.json",
            "implementation.json",
        )
    }
    if variant != "B0":
        allowed_files.add(root / PARENT / "training" / variant / "adapter.safetensors")
    allowed_trees = [root / OUTPUT / phase / variant]
    if phase == "scoring":
        allowed_files.add(prep / "weight_view.json")
        allowed_trees += [root / SOURCE / "closeout"]
        # load_rows verifies the exact original tokenizer binding/policy references.
        allowed_files |= {
            root / SOURCE / "preparation" / name
            for name in ("tokenizer_binding.json", "representation_policy.json")
        }
    elif phase == "generation":
        allowed_files.add(prep / "public/L1.json")
    else:
        raise ValueError("diagnostic.phase")
    assets = root / (
        "trusted_data_synthesis/artifacts/qa_vnext_finqa_support_exploration/"
        "j1_j2_nd_3rep_20260908/preparation"
    )
    allowed_files |= {assets / n for n in ("tokenizer_binding.json", "representation_policy.json")}
    # These are exact metadata files, not the old public trajectories or target arrays.
    counts = {"cross_phase_artifact_access": 0}
    originals = [(builtins, "open"), (io, "open"), (os, "open")]

    def wrap(original):
        def checked(file, *args, **kwargs):
            if isinstance(file, (str, bytes, Path)):
                path = Path(os.fsdecode(file)).resolve()
                if (
                    path.is_relative_to(artifact_root)
                    and not path.is_dir()
                    and not (
                        path in allowed_files or any(path.is_relative_to(p) for p in allowed_trees)
                    )
                ):
                    counts["cross_phase_artifact_access"] += 1
                    raise PermissionError("diagnostic.forbidden_phase_artifact")
            return original(file, *args, **kwargs)

        return checked

    with offline_guard() as network, ExitStack() as stack:
        for owner, name in originals:
            stack.enter_context(patch.object(owner, name, wrap(getattr(owner, name))))
        yield counts, network


@contextmanager
def inference_only():
    """Installed after checkpoint restoration and before any diagnostic forward."""
    import torch

    counts = {}

    def block(name):
        counts[name] = 0

        def fail(*args, **kwargs):
            counts[name] += 1
            raise RuntimeError("diagnostic.inference_only." + name)

        return fail

    original_train = torch.nn.Module.train
    counts["training_mode"] = 0

    def train(module, mode=True):
        if mode:
            counts["training_mode"] += 1
            raise RuntimeError("diagnostic.inference_only.training_mode")
        return original_train(module, mode)

    with ExitStack() as stack:
        for owner, name, label in (
            (torch.optim.Optimizer, "__init__", "optimizer_construction"),
            (torch.Tensor, "backward", "tensor_backward"),
            (torch.autograd, "backward", "autograd_backward"),
            (torch.autograd, "grad", "autograd_grad"),
        ):
            stack.enter_context(patch.object(owner, name, block(label)))
        stack.enter_context(patch.object(torch.nn.Module, "train", train))
        stack.enter_context(torch.inference_mode())
        yield counts


def parameter_fingerprint(model, chunk_bytes=16 * 1024 * 1024):
    """Hash every base and adapter parameter byte, in bounded host-memory chunks."""
    import torch

    require(all(not m.training for m in model.modules()), "diagnostic.eval_all_modules")
    require(not getattr(model, "is_gradient_checkpointing", False), "diagnostic.no_checkpointing")
    digest, members, total, nbytes = hashlib.sha256(), [], 0, 0
    for name, parameter in sorted(model.named_parameters()):
        require(
            not parameter.requires_grad and parameter.grad is None, "diagnostic.frozen_parameter"
        )
        metadata = {"name": name, "shape": list(parameter.shape), "dtype": str(parameter.dtype)}
        digest.update(encode(metadata))
        raw = parameter.detach().contiguous().reshape(-1).view(torch.uint8)
        own = hashlib.sha256()
        for start in range(0, raw.numel(), chunk_bytes):
            chunk = raw[start : start + chunk_bytes].cpu().numpy()
            own.update(memoryview(chunk))
            digest.update(memoryview(chunk))
        members.append({**metadata, "sha256": own.hexdigest(), "version": parameter._version})
        total += parameter.numel()
        nbytes += raw.numel()
    return record(
        "all_parameter_fingerprint",
        sha256=digest.hexdigest(),
        parameter_count=total,
        parameter_bytes=nbytes,
        named_tensors=len(members),
        members=members,
        all_requires_grad_false=True,
        all_grad_none=True,
        all_modules_eval=True,
    )


def assert_unchanged(before, after):
    require(before == after, "diagnostic.parameter_bytes_or_versions_changed")


def guard_record(phase, counts, network, updates):
    require(
        not any(v for group in (counts, network, updates) for v in group.values()),
        "diagnostic.forbidden_calls_observed",
    )
    return record(
        "inference_guard_report",
        phase=phase,
        artifact_calls=counts,
        network_calls=network,
        training_calls=updates,
        all_zero=True,
        checkpoint_restoration_precedes_update_guard=True,
        scope=(
            "instrumented Python entry points and actual request audit; "
            "not arbitrary-code isolation"
        ),
    )
