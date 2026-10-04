"""CPU/source-only compatibility checks; no tensors, provider imports or API."""

import importlib.util
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "finqa_v22_provider_compat", PROJECT / "scripts/finqa_v22_provider_compat.py"
)
compat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compat)

FIXTURE = b"""class LocalTorchProvider:
    def chat(self):
        return 'local-only'

class DeepSeekFlashProvider:
    async def chat(self):
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            return client
"""


def test_synthetic_ast_fixture_is_only_the_api_keyword_edit():
    normalized, evidence = compat._normalize_exact_api_edit(FIXTURE)
    assert normalized == FIXTURE.replace(b", trust_env=False", b"")
    assert evidence["class_name"] == "DeepSeekFlashProvider"
    assert evidence["method_name"] == "chat"
    assert evidence["local_inference_source_unchanged"] is True
    assert evidence["all_other_file_bytes_unchanged"] is True


@pytest.mark.parametrize(
    "source",
    [
        FIXTURE.replace(b"trust_env=False", b"trust_env=True"),
        FIXTURE + b"\n# httpx.AsyncClient(timeout=self.timeout, trust_env=False)\n",
        FIXTURE.replace(b"DeepSeekFlashProvider", b"DifferentProvider"),
        FIXTURE.replace(b"async def chat", b"async def another_method"),
        FIXTURE.replace(b"LocalTorchProvider", b"DifferentLocalProvider"),
        FIXTURE.replace(b"async with httpx", b"async with invalid httpx"),
        b"# httpx.AsyncClient(timeout=self.timeout, trust_env=False)\n",
    ],
)
def test_private_ast_check_rejects_nonexact_edits_and_wrong_scope(source):
    with pytest.raises(ValueError):
        compat._normalize_exact_api_edit(source)


def test_public_api_cannot_admit_fixture_by_supplying_its_hashes():
    normalized, _ = compat._normalize_exact_api_edit(FIXTURE)
    with pytest.raises(ValueError, match="exact registered Base/V18"):
        compat.prove_provider_compatibility(
            FIXTURE,
            base_sha256=compat._sha(normalized),
            current_sha256=compat._sha(FIXTURE),
        )
    with pytest.raises(ValueError, match="actual provider source hash changed"):
        compat.prove_provider_compatibility(
            FIXTURE,
            base_sha256=compat.BASE_PROVIDERS_SHA256,
            current_sha256=compat.CURRENT_PROVIDERS_SHA256,
        )


def test_real_source_has_only_the_registered_nonlocal_edit():
    # Read source bytes only, never import the provider or initialize torch/CUDA.
    current = (PROJECT / "src/trusted_synthesis/finance_research/providers.py").read_bytes()
    proof = compat.prove_provider_compatibility(
        current,
        base_sha256=compat.BASE_PROVIDERS_SHA256,
        current_sha256=compat.CURRENT_PROVIDERS_SHA256,
    )
    assert proof["actual_sha256"] == compat.CURRENT_PROVIDERS_SHA256
    assert proof["normalized_sha256"] == compat.BASE_PROVIDERS_SHA256
    assert proof["API_calls"] == 0
    assert proof["GPU_execution_performed"] is False
    assert proof["numerical_equivalence_measured"] is False
    assert proof["runtime_hash_rewritten"] is False
    with pytest.raises(ValueError, match="actual provider source hash changed"):
        compat.prove_provider_compatibility(
            current + b"\n# unrelated source mutation\n",
            base_sha256=compat.BASE_PROVIDERS_SHA256,
            current_sha256=compat.CURRENT_PROVIDERS_SHA256,
        )
