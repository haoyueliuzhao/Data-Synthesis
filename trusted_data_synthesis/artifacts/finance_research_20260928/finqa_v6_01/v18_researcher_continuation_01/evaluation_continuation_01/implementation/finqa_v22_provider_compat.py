"""Exact offline source proof for the single frozen V18/Base API-only edit.

This does not relax any general runtime guard, import either provider, call an
API, or claim numerical/GPU equivalence. The public API admits one known pair of
whole-file hashes; synthetic AST fixtures exercise only the private helper.
"""

from __future__ import annotations

import ast
import hashlib

BASE_PROVIDERS_SHA256 = "d22c7836aab85a4ace9e98559e20d0d207cb79755ce90be9eae5f82b13c555d9"
CURRENT_PROVIDERS_SHA256 = "add33ed7e4229b87ed5e0766d73b4f14e2c5f6a3ec69a92475f77d51715f1f01"

_OLD_CALL = b"httpx.AsyncClient(timeout=self.timeout)"
_NEW_CALL = b"httpx.AsyncClient(timeout=self.timeout, trust_env=False)"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _normalize_exact_api_edit(current_source: bytes):
    """Validate syntax/location of the exact edit; does not grant admission."""
    _require(type(current_source) is bytes, "provider source must be bytes")
    _require(current_source.count(_NEW_CALL) == 1, "exact API constructor must occur once")
    normalized = current_source.replace(_NEW_CALL, _OLD_CALL, 1)
    try:
        current_text = current_source.decode("utf-8")
        normalized_text = normalized.decode("utf-8")
        current_tree = ast.parse(current_text)
        normalized_tree = ast.parse(normalized_text)
    except (UnicodeError, SyntaxError) as error:
        raise ValueError("provider source must be valid UTF-8 Python") from error

    class CallLocator(ast.NodeVisitor):
        def __init__(self):
            self.scopes, self.matches = [], []

        def visit_scope(self, node):
            self.scopes.append((type(node).__name__, node.name))
            self.generic_visit(node)
            self.scopes.pop()

        visit_ClassDef = visit_scope
        visit_FunctionDef = visit_scope
        visit_AsyncFunctionDef = visit_scope

        def visit_Call(self, node):
            if ast.get_source_segment(current_text, node) == _NEW_CALL.decode():
                self.matches.append((node, tuple(self.scopes)))
            self.generic_visit(node)

    locator = CallLocator()
    locator.visit(current_tree)
    _require(
        len(locator.matches) == 1, "allowed edit must be one real AST call, not a string/comment"
    )
    call, scopes = locator.matches[0]
    _require(
        scopes == (("ClassDef", "DeepSeekFlashProvider"), ("AsyncFunctionDef", "chat")),
        "allowed edit must belong only to DeepSeekFlashProvider.chat",
    )
    _require(
        len(
            [
                node
                for node in current_tree.body
                if isinstance(node, ast.ClassDef) and node.name == "DeepSeekFlashProvider"
            ]
        )
        == 1,
        "unique top-level DeepSeekFlashProvider required",
    )
    _require(
        [keyword.arg for keyword in call.keywords] == ["timeout", "trust_env"]
        and isinstance(call.keywords[1].value, ast.Constant)
        and call.keywords[1].value.value is False,
        "only the literal trust_env=False keyword may be removed",
    )
    call.keywords.pop()
    _require(
        ast.dump(current_tree, include_attributes=False)
        == ast.dump(normalized_tree, include_attributes=False),
        "AST may differ only by the allowed API keyword",
    )
    local_classes = [
        node
        for node in current_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "LocalTorchProvider"
    ]
    normalized_local = [
        node
        for node in normalized_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "LocalTorchProvider"
    ]
    _require(
        len(local_classes) == len(normalized_local) == 1,
        "unique top-level LocalTorchProvider required",
    )
    local_source = ast.get_source_segment(current_text, local_classes[0])
    _require(
        local_source == ast.get_source_segment(normalized_text, normalized_local[0]),
        "LocalTorchProvider source must remain byte-identical",
    )
    return normalized, dict(
        class_name="DeepSeekFlashProvider",
        method_name="chat",
        allowed_edit=dict(
            before=_OLD_CALL.decode(),
            after=_NEW_CALL.decode(),
            occurrence_count=1,
            AST_change="one literal trust_env=False keyword on the API HTTP client",
        ),
        local_inference_source_unchanged=True,
        local_provider_source_sha256=_sha(local_source.encode("utf-8")),
        all_other_file_bytes_unchanged=True,
    )


def prove_provider_compatibility(
    current_source: bytes, *, base_sha256: str, current_sha256: str
) -> dict:
    """Admit only the pinned Base/V18 pair; no caller-selectable hash bypass."""
    _require(
        base_sha256 == BASE_PROVIDERS_SHA256 and current_sha256 == CURRENT_PROVIDERS_SHA256,
        "only the exact registered Base/V18 provider hash pair is admitted",
    )
    _require(type(current_source) is bytes, "provider source must be bytes")
    actual_sha256 = _sha(current_source)
    _require(actual_sha256 == CURRENT_PROVIDERS_SHA256, "actual provider source hash changed")
    normalized, evidence = _normalize_exact_api_edit(current_source)
    normalized_sha256 = _sha(normalized)
    _require(
        normalized_sha256 == BASE_PROVIDERS_SHA256,
        "exact inverse edit must reproduce the whole frozen Base provider hash",
    )
    return dict(
        schema="v22_exact_api_only_provider_source_compatibility.v1",
        base_sha256=base_sha256,
        current_sha256=current_sha256,
        actual_sha256=actual_sha256,
        normalized_sha256=normalized_sha256,
        **evidence,
        API_calls=0,
        GPU_execution_performed=False,
        numerical_equivalence_measured=False,
        proof_scope=(
            "exact source-only edit outside LocalTorchProvider; "
            "not an API behavior equivalence claim"
        ),
        required_execution_backend="local_torch",
        runtime_hash_rewritten=False,
        Base_source_or_protocol_modified=False,
    )
