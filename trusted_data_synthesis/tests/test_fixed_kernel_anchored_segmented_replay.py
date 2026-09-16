"""One new tiny-Qwen full-graph/adjoint test, not a real Student/GPU claim."""

import importlib
import sys
from pathlib import Path

import torch
from transformers import Qwen2Config, Qwen2ForCausalLM

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
seg = importlib.import_module("fixed_kernel_anchored_segmented_replay_20260916")
r2 = importlib.import_module("fixed_kernel_anchored_sources_cached_replay_20260916")


def test_boundary_adjoint_and_pure_prefill_equal_full_graph_without_state_mutation():
    torch.manual_seed(19)
    config = Qwen2Config(
        vocab_size=17,
        hidden_size=8,
        intermediate_size=16,
        num_hidden_layers=2,
        num_attention_heads=2,
        num_key_value_heads=1,
        attention_dropout=0.0,
        max_position_embeddings=32768,
    )
    config._attn_implementation = "sdpa"
    model = Qwen2ForCausalLM(config).float()
    model.requires_grad_(False)
    model.model.layers[0].self_attn.q_proj.weight.requires_grad_(True)
    named = {name: value for name, value in model.named_parameters() if value.requires_grad}
    theta = {
        name: (value.detach().clone() + 0.01).requires_grad_(True) for name, value in named.items()
    }
    prompt, targets = [2, 3, 5, 7], [1, 4, 6, 8, 10, 12]
    before = {name: value.detach().clone() for name, value in named.items()}
    rng = torch.get_rng_state().clone()
    full, derivative = r2.cached_logp(model, theta, prompt, targets, offload=False)
    actual, gradient, accounting = seg.segmented_logp(
        model,
        theta,
        prompt,
        targets,
        expected=full.tolist(),
        block_size=2,
        prefill_checkpoint=True,
        offload=False,
    )
    assert torch.allclose(actual, full, atol=1e-6, rtol=1e-5)
    for name in named:
        assert torch.allclose(gradient[name], derivative[name], atol=1e-6, rtol=1e-5)
        assert torch.equal(named[name], before[name]) and named[name].grad is None
    assert accounting["complete_prefix_adjoint_included"] and accounting["decode_blocks"] == 3
    assert torch.equal(torch.get_rng_state(), rng) and model.training
    assert all("forward" not in layer.__dict__ for layer in model.model.layers)
