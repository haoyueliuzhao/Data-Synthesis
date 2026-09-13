"""Model-point class gradients and a non-persistent functional virtual model."""

import hashlib
from collections import Counter
from contextlib import contextmanager, nullcontext

import torch
from torch import nn
from torch.nn.attention import SDPBackend, sdpa_kernel

from ..finance_qa_vnext_basis_student.kernel import validate_row
from ..finance_qa_vnext_pq_student.loss import selected_target_loss
from . import protocol as p


def tensor_digest(values):
    digest = hashlib.sha256()
    for name, value in sorted(values.items()):
        digest.update(
            p.encode({"name": name, "shape": list(value.shape), "dtype": str(value.dtype)})
        )
        digest.update(
            value.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
        )
    return digest.hexdigest()


@contextmanager
def evaluation_mode(model):
    modes = [(module, module.training) for module in model.modules()]
    model.eval()
    try:
        yield
    finally:
        for module, training in modes:
            module.training = training


def _named_trainables(model):
    values = {name: value for name, value in model.named_parameters() if value.requires_grad}
    p.require(
        bool(values) and all(value.is_floating_point() for value in values.values()),
        "gradients.nonempty_named_trainables",
    )
    return values


def class_gradients(model, packages):
    """Mean package NLL gradients, not probabilities or reward gradients.

    Packages are already authenticated by state_materials. This routine also
    checks their complete token denominators. No optimizer step or .grad
    accumulation occurs; dropout is off only for the declared feedback proxy.
    """
    parameters = _named_trainables(model)
    before = tensor_digest(dict(model.named_parameters()))
    before_buffers = tensor_digest(dict(model.named_buffers()))
    old_grads = {
        name: None if value.grad is None else value.grad.detach().clone()
        for name, value in parameters.items()
    }
    packages = list(packages)
    p.require(
        packages and len({row["package_id"] for row in packages}) == len(packages),
        "gradients.unique_complete_fixed_packages",
    )
    p.require(len({row["pool"] for row in packages}) == 1, "gradients.one_material_pool")
    counts = Counter((row["task_id"], row["state_id"]) for row in packages)
    gradients = {}
    rows_count = targets = sequences = 0
    try:
        with evaluation_mode(model):
            for package in packages:
                p.require(package.get("role", "train") == "train", "gradients.no_heldout_feedback")
                task, state = package["task_id"], package["state_id"]
                values = gradients.setdefault(task, {}).setdefault(
                    state, {name: torch.zeros_like(value) for name, value in parameters.items()}
                )
                validated = [validate_row(row) for row in package["rows"]]
                length = sum(row["target_token_count"] for row in validated)
                p.require(
                    length > 0 and length == package["whole_package_target_tokens"],
                    "gradients.original_whole_package_L",
                )
                for row in validated:
                    device = next(iter(parameters.values())).device
                    ids = torch.tensor([row["input_ids"]], dtype=torch.long, device=device)
                    positions = [index for index, mask in enumerate(row["target_mask"]) if mask]
                    selected = torch.tensor([index - 1 for index in positions], device=device)
                    labels = [row["labels"][index] for index in positions]
                    context = (
                        sdpa_kernel(SDPBackend.FLASH_ATTENTION)
                        if device.type == "cuda"
                        else nullcontext()
                    )
                    with context:
                        logits = model(
                            input_ids=ids,
                            attention_mask=torch.ones_like(ids),
                            use_cache=False,
                            logits_to_keep=selected,
                        ).logits
                        loss = selected_target_loss(
                            logits, labels, 1 / (counts[task, state] * length)
                        )
                        p.require(
                            loss.requires_grad and bool(torch.isfinite(loss)),
                            "gradients.finite_connected_loss",
                        )
                        row_gradients = torch.autograd.grad(
                            loss, tuple(parameters.values()), allow_unused=True
                        )
                    for (name, _parameter), gradient in zip(
                        parameters.items(), row_gradients, strict=True
                    ):
                        if gradient is not None:
                            p.require(
                                bool(torch.isfinite(gradient).all()),
                                "gradients.finite_class_gradient",
                            )
                            values[name] += gradient.detach()
                    rows_count += 1
                    targets += len(labels)
                    sequences += len(row["input_ids"])
        p.require(
            tensor_digest(dict(model.named_parameters())) == before,
            "gradients.no_parameter_mutation",
        )
        p.require(
            tensor_digest(dict(model.named_buffers())) == before_buffers,
            "gradients.no_buffer_mutation",
        )
        for name, parameter in parameters.items():
            old = old_grads[name]
            p.require(
                (old is None and parameter.grad is None)
                or (
                    old is not None
                    and parameter.grad is not None
                    and torch.equal(old, parameter.grad)
                ),
                "gradients.no_optimizer_grad_buffer_mutation",
            )
    except BaseException:
        # Fail without any attempted optimization or automatic recovery.
        raise
    artifact = p.record(
        "class_gradient_evidence",
        model_parameter_digest=before,
        model_buffer_digest=before_buffers,
        package_count=len(packages),
        state_counts={
            task: {state: counts[task, state] for state in states}
            for task, states in gradients.items()
        },
        class_gradient_digests={
            task: {state: tensor_digest(value) for state, value in states.items()}
            for task, states in gradients.items()
        },
        original_package_ids=[row["package_id"] for row in packages],
        forward_backward_rows=rows_count,
        target_tokens=targets,
        sequence_tokens=sequences,
        loss="mean package NLL within class, each package mean over its original target tokens",
        proxy_dropout=False,
        real_parameters_or_optimizer_updated=False,
        same_as_greedy_trajectory_utility=False,
    )
    return {"gradients": gradients, "artifact": artifact}


class FunctionalStudent(nn.Module):
    """Virtual trainables and cloned buffers; original parameter storage untouched.

    This is a single-owner model view. functional_call temporarily substitutes
    attributes during forward, not a concurrently shared model execution API.
    No SFT update is applied to this view.
    """

    def __init__(self, model, theta_bar):
        super().__init__()
        original = _named_trainables(model)
        p.require(set(original) == set(theta_bar), "virtual.exact_trainable_parameter_set")
        object.__setattr__(self, "_base_model", model)
        self._names = sorted(theta_bar)
        self._values = nn.ParameterList()
        for name in self._names:
            value = theta_bar[name]
            p.require(
                value.shape == original[name].shape
                and value.dtype == original[name].dtype
                and value.device == original[name].device
                and bool(torch.isfinite(value).all()),
                "virtual.bound_shape_dtype_device",
            )
            self._values.append(nn.Parameter(value.detach().clone(), requires_grad=True))
        self._buffer_copies = {
            name: value.detach().clone() for name, value in model.named_buffers()
        }
        self._base_digest = tensor_digest(dict(model.named_parameters()))
        self._base_buffer_digest = tensor_digest(dict(model.named_buffers()))
        self.eval()

    def named_parameters(self, prefix="", recurse=True, remove_duplicate=True):
        for name, value in zip(self._names, self._values, strict=True):
            yield ((prefix + "." if prefix else "") + name), value

    def named_buffers(self, prefix="", recurse=True, remove_duplicate=True):
        for name, value in sorted(self._buffer_copies.items()):
            yield ((prefix + "." if prefix else "") + name), value

    def forward(self, *args, **kwargs):
        parameters = dict(self.named_parameters())
        overrides = {**parameters, **self._buffer_copies}
        with evaluation_mode(self._base_model):
            return torch.func.functional_call(
                self._base_model, overrides, args, kwargs, strict=False
            )

    def assert_original_unchanged(self):
        p.require(
            tensor_digest(dict(self._base_model.named_parameters())) == self._base_digest
            and tensor_digest(dict(self._base_model.named_buffers())) == self._base_buffer_digest,
            "virtual.original_model_changed",
        )
        return True
