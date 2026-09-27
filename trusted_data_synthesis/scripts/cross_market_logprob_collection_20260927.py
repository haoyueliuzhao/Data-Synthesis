"""Collect unchanged per-token log probabilities with one device-to-host transfer.

This opt-in adapter performs no model loading, generation, or artifact writes.
The frozen Decoder source remains untouched; only its post-sampling ``logps``
assignment is replaced in a private copy of ``Decoder.__call__``. No generation,
RNG, parameter, precision, attention, or receipt logic is replaced.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import textwrap
from pathlib import Path

import torch

SOURCE_FILENAME = "fixed_kernel_anchored_feedback_20260916.py"
SOURCE_SHA256 = "d77eb25c0693ae245878522667bf38d31ef63282d11e872c75b36cd6613e60fb"
_HELPER_NAME = "_cross_market_collected_logprobs"
_ORIGINAL_ASSIGNMENT = """
logps = [
    float(torch.log_softmax(score[0].float(), -1)[token])
    for token, score in zip(output, result.scores, strict=True)
]
"""
_REPLACEMENT_ASSIGNMENT = f"logps = {_HELPER_NAME}(output, result.scores)"


def collected_logprobs(output, scores):
    """Keep each row's FP32 log_softmax, then copy only selected scalar values.

    Cloning the selected scalar prevents its view from retaining a whole
    vocabulary-sized log_softmax output. The additional retained tensors have
    one element per generated token, never one vocabulary row per token.
    ``zip(strict=True)`` preserves the original length-mismatch rejection.
    """
    selected = [
        torch.log_softmax(score[0].float(), -1)[token].clone()
        for token, score in zip(output, scores, strict=True)
    ]
    return torch.stack(selected).cpu().tolist() if selected else []


def _ast_text(tree):
    return ast.dump(tree, include_attributes=False)


def _sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def _replace_collection(tree):
    """Fail closed unless exactly the registered assignment can be replaced."""
    original = ast.parse(textwrap.dedent(_ORIGINAL_ASSIGNMENT)).body[0]
    replacement = ast.parse(_REPLACEMENT_ASSIGNMENT).body[0]
    before = _ast_text(tree)
    matches = [node for node in ast.walk(tree) if _ast_text(node) == _ast_text(original)]
    if len(matches) != 1:
        raise ValueError("logprob_collection.exactly_one_original_assignment")
    if any(isinstance(node, ast.Name) and node.id == _HELPER_NAME for node in ast.walk(tree)):
        raise ValueError("logprob_collection.no_existing_helper_name")

    class Replace(ast.NodeTransformer):
        def visit_Assign(self, node):
            if _ast_text(node) == _ast_text(original):
                return ast.copy_location(copy.deepcopy(replacement), node)
            return self.generic_visit(node)

    changed = Replace().visit(copy.deepcopy(tree))

    class Restore(ast.NodeTransformer):
        def visit_Assign(self, node):
            if _ast_text(node) == _ast_text(replacement):
                return ast.copy_location(copy.deepcopy(original), node)
            return self.generic_visit(node)

    restored = Restore().visit(copy.deepcopy(changed))
    if _ast_text(restored) != before:
        raise ValueError("logprob_collection.all_other_AST_unchanged")
    return ast.fix_missing_locations(changed)


def optimized_decoder_class():
    """Return an isolated Decoder subclass plus an inspectable source binding.

    The returned class exposes ``logprob_collection_binding``. Callers must
    register this adapter separately before enabling it in a frozen experiment;
    calling this factory does not enable it or patch the original module.
    """
    import fixed_kernel_anchored_feedback_20260916 as frozen

    source_path = Path(frozen.__file__).resolve()
    source_digest = _sha(source_path.read_bytes())
    if source_path.name != SOURCE_FILENAME or source_digest != SOURCE_SHA256:
        raise ValueError("logprob_collection.exact_frozen_source_bytes")
    original = frozen.Decoder.__call__
    source = textwrap.dedent(inspect.getsource(original))
    tree = ast.parse(source)
    changed = _replace_collection(tree)
    namespace = {**original.__globals__, _HELPER_NAME: collected_logprobs}
    code = compile(changed, str(source_path) + "[logprob-collection]", "exec")
    exec(code, namespace)
    optimized = namespace[original.__name__]
    optimized.__qualname__ = "CollectedLogprobDecoder.__call__"
    binding = {
        "source_filename": SOURCE_FILENAME,
        "source_sha256": source_digest,
        "original_call_source_sha256": _sha(source),
        "original_call_ast_sha256": _sha(_ast_text(tree)),
        "optimized_call_ast_sha256": _sha(_ast_text(changed)),
        "helper_source_sha256": _sha(Path(__file__).read_bytes()),
        "changed_assignment_count": 1,
        "all_other_AST_unchanged": True,
        "per_row_log_softmax_shape_and_dtype_unchanged": True,
        "selected_scalars_cloned_before_stack": True,
        "host_transfers_per_nonempty_collection": 1,
    }
    return type(
        "CollectedLogprobDecoder",
        (frozen.Decoder,),
        {
            "__module__": __name__,
            "__doc__": "Frozen Decoder with only post-sampling logprob collection replaced.",
            "__call__": optimized,
            "logprob_collection_binding": binding,
        },
    )
