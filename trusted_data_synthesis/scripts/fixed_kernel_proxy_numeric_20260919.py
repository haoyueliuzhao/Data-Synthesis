"""Saved-point Adam pullback references; no mutation of the registered optimizer.

The stable expression cancels the cold-start h**2 terms algebraically, not by
clipping a negative derivative. General nonempty-moment derivatives may be negative.
"""

import math

import torch


def local_diagonal(h, first, second, step, config, *, stable):
    b1, b2, eps = config["beta1"], config["beta2"], config["eps"]
    one, two = 1 - b1, 1 - b2
    first_next = torch.lerp(first, h, one)
    second_next = torch.addcmul(second * b2, h, h, value=two)
    root = second_next.sqrt()
    root_correction = math.sqrt(1 - b2 ** (step + 1))
    denominator = root / root_correction + eps
    scale = config["lr"] / (1 - b1 ** (step + 1))
    zero = root == 0
    if bool((zero & ((h != 0) | (first_next != 0))).any()):
        raise ValueError("nondifferentiable zero second moment")
    safe_root = torch.where(zero, torch.ones_like(root), root)
    if stable:
        # (1-b1)*v_next - (1-b2)*m_next*h
        # = (1-b1)*b2*v - b1*(1-b2)*m*h: h**2 cancels exactly.
        numerator = (one * b2 * second - b1 * two * first * h) / (
            root_correction * safe_root
        ) + one * eps
        result = scale * numerator / denominator.square()
    else:
        d_denominator = two * h / (safe_root * root_correction)
        result = scale * (one / denominator - first_next * d_denominator / denominator.square())
    return result


def pullback(G, first, second, covector, blocks, groups, clip, *, stable=True, dtype=torch.float64):
    """DU(G)^T covector, with the complete global L2 clipping derivative."""
    G, first, second, covector = (x.detach().to(dtype) for x in (G, first, second, covector))
    norms = [
        torch.linalg.vector_norm(G[b["start"] : b["stop"]].reshape(b["shape"]), 2.0) for b in blocks
    ]
    norm = torch.linalg.vector_norm(torch.stack(norms), 2.0)
    limit, epsilon = clip["max_norm"], clip["epsilon"]
    coefficient = (
        torch.ones_like(norm) if limit is None else torch.clamp(limit / (norm + epsilon), max=1.0)
    )
    active = bool(coefficient < 1)
    diagonal = torch.empty_like(G)
    for block in blocks:
        sl = slice(block["start"], block["stop"])
        group = groups[block["group"]]
        sign = -1 if group["maximize"] else 1
        h = G[sl] * coefficient * sign
        diagonal[sl] = (
            local_diagonal(h, first[sl], second[sl], block["step"], group, stable=stable) * sign
        )
    scaled = diagonal * covector
    if active and norm.item() != 0:
        radial = torch.dot(scaled, G) / (norm * (norm + epsilon))
        result = coefficient * (scaled - radial * G)
    else:
        result = coefficient * scaled
    if not bool(torch.isfinite(result).all() and torch.isfinite(diagonal).all()):
        raise ValueError("nonfinite reference pullback")
    return result, dict(
        norm=float(norm),
        coefficient=float(coefficient),
        active=active,
        negative_diagonal_coordinates=int((diagonal < 0).sum()),
        dtype=str(dtype),
        stable=stable,
    )


def compare(candidate, reference):
    candidate, reference = candidate.detach().double(), reference.detach().double()
    error = candidate - reference
    n_ref, n_candidate = float(reference.norm()), float(candidate.norm())
    meaningful = reference.abs() >= max(float(reference.abs().max()) * 1e-6, 1e-30)
    cosine = (
        float(torch.dot(candidate, reference) / (n_ref * n_candidate))
        if n_ref and n_candidate
        else None
    )
    return dict(
        coordinates=reference.numel(),
        max_absolute=float(error.abs().max()),
        L2_error=float(error.norm()),
        reference_L2=n_ref,
        candidate_L2=n_candidate,
        relative_L2=float(error.norm()) / max(n_ref, 1e-30),
        cosine=cosine,
        sign_disagreements=int((candidate.sign() != reference.sign()).sum()),
        sign_disagreements_reference_above_1e_minus6_max=int(
            ((candidate.sign() != reference.sign()) & meaningful).sum()
        ),
    )


def cold_counterexample():
    config = dict(beta1=0.9, beta2=0.999, eps=1e-8, lr=1e-4)
    h = torch.tensor([0.1], dtype=torch.float32)
    zero = torch.zeros_like(h)
    original = local_diagonal(h, zero, zero, 0, config, stable=False)
    stable = local_diagonal(h.double(), zero.double(), zero.double(), 0, config, stable=True)
    exact = config["lr"] * config["eps"] / (h.double().abs() + config["eps"]).square()
    return dict(
        torch_version=str(torch.__version__),
        device="cpu",
        input_FP32=float(h[0]),
        original_FP32=float(original[0]),
        stable_FP64=float(stable[0]),
        real_formula_at_same_representable_input=float(exact[0]),
        sign_flip_observed=bool(original[0] < 0 < stable[0]),
        original_CUDA_run_reproduced=False,
        historical_effect_not_inferred_from_scalar=True,
    )
