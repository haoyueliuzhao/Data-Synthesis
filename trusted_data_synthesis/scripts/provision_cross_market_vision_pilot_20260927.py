"""Offline, committed file-level VLM plan; no downloader, installer or model call.

The official torchvision wheel HEAD denial remains unresolved. A later source
build or dependency acquisition must have its own frozen protocol and authority.
This module cannot download weights, create an environment or issue certificates.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

import prepare_cross_market_sources_20260926 as base

SCRIPT = "trusted_data_synthesis/scripts/provision_cross_market_vision_pilot_20260927.py"
RAW = base.RAW / "original_evidence_revision_02" / "vision_runtime_provision_01"
PROTOCOL = "cross_market_vision_provision_protocol"
REPO = "OpenGVLab/InternVL3_5-8B-HF"
REVISION = "741a7d03020411e666c6109218ab71e08151ef86"
SOURCE_PYTHON = base.ROOT_DATA / "trusted_data_synthesis/.venv/bin/python"
MAX_WEIGHT_BYTES = 20_000_000_000
MAX_METADATA_BYTES = 32 * 2**20
EXPECTED_VERSIONS = {"torch": "2.7.1+cu128", "transformers": "5.14.1"}
# Official HF API ?blobs=true, HTTP 200 on 2026-09-27; no weight bytes read.
# Non-LFS hashes are Git object SHA-1 including blob header, NOT file SHA-256.
MODEL_FILES = (
    ("README.md", 43006, "git_blob_sha1", "bbd87a4cc296c77608f66adfe9411b6c7e84b1e8"),
    ("added_tokens.json", 913, "git_blob_sha1", "3ecaee9890f76c964b4bf550a85293b874b71b87"),
    ("chat_template.jinja", 481, "git_blob_sha1", "0b19f45e0cd40b10374f24065639b0c2eee18a22"),
    ("config.json", 2998, "git_blob_sha1", "e649dc4968d1a55b93277a3ee38951308c43b7c8"),
    ("generation_config.json", 121, "git_blob_sha1", "4f0c4ce3e3028b76812135c422c721c3e77b10b6"),
    ("merges.txt", 1671853, "git_blob_sha1", "31349551d90c7606f325fe0f11bbb8bd5fa0d7c7"),
    (
        "model-00001-of-00004.safetensors",
        4906355392,
        "sha256",
        "541b630d4a991a0f9502b87b7e7fa3a4a3b03bc0fec4a9057eeb0af35873beae",
    ),
    (
        "model-00002-of-00004.safetensors",
        4915962480,
        "sha256",
        "1dd4d7629deff34807654ca198f45166a532fdbc1bbda3fd80e5e69eebdcdcd4",
    ),
    (
        "model-00003-of-00004.safetensors",
        4915962496,
        "sha256",
        "595f3b9043d046ae612f2dbf7cbfcd2465a1c001fcb58e93f78dcaf7cc5976e1",
    ),
    (
        "model-00004-of-00004.safetensors",
        2318463688,
        "sha256",
        "1935bfbc7774be5e64adf7ecec5cbefc7c18dae24d498ba4609301c3423b21fd",
    ),
    (
        "model.safetensors.index.json",
        79937,
        "git_blob_sha1",
        "7dd68ac44f79c16f239653f1b51600ceec4dab04",
    ),
    ("preprocessor_config.json", 666, "git_blob_sha1", "a7b376e0a83f26eaa784db792ef61be7aac5494f"),
    ("processor_config.json", 72, "git_blob_sha1", "e543bcb3b7550029f450d28cf138706d7f9a5ef5"),
    ("special_tokens_map.json", 877, "git_blob_sha1", "253d50d9027f558bd5478163a49ccd263fc27959"),
    (
        "tokenizer.json",
        11424484,
        "sha256",
        "7b9d18660f656ae5a87df2d5d6ed990e80f292d3473c1a35cae8259a5d28cd67",
    ),
    ("tokenizer_config.json", 7614, "git_blob_sha1", "16f34ecc26e1a1c213ab719189e1407e3e200196"),
    (
        "video_preprocessor_config.json",
        1345,
        "git_blob_sha1",
        "312440223df86c67a0794043b915a0422a685971",
    ),
    ("vocab.json", 2776833, "git_blob_sha1", "4783fe10ac3adce15ac8f358ef5462739852c569"),
)
WHEELS = (
    dict(
        name="Pillow",
        version="12.3.0",
        bytes=6940830,
        filename="pillow-12.3.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl",
        sha256="78cb2c6865a35ab8ff8b75fd122f6033b92a62c82801110e48ddd6c936a45d91",
        metadata_source="https://pypi.org/pypi/Pillow/12.3.0/json",
        status="METADATA_ONLY_NOT_DOWNLOADED",
    ),
    dict(
        name="torchvision",
        version="0.22.1+cu128",
        bytes=None,
        filename="torchvision-0.22.1+cu128-cp312-cp312-manylinux_2_28_x86_64.whl",
        sha256="f64ef9bb91d71ab35d8384912a19f7419e35928685bc67544d58f45148334373",
        metadata_source="https://download.pytorch.org/whl/cu128/torchvision/",
        status="OFFICIAL_WHEEL_HEAD_403_NO_RETRY_OR_ALTERNATE_ROUTE",
        official_wheel_url="https://download-r2.pytorch.org/whl/cu128/"
        "torchvision-0.22.1%2Bcu128-cp312-cp312-manylinux_2_28_x86_64.whl",
    ),
)


def manifest():
    rows = [
        dict(
            filename=n,
            bytes=s,
            hash_kind=k,
            expected_hash=h,
            role="weights" if n.endswith(".safetensors") else "metadata",
            url=f"https://huggingface.co/{REPO}/resolve/{REVISION}/{n}",
        )
        for n, s, k, h in MODEL_FILES
    ]
    weights = [r for r in rows if r["role"] == "weights"]
    base.require(
        len(rows) == 18 and len(weights) == 4 and len({r["filename"] for r in rows}) == 18,
        "vision_exact_file_scope",
    )
    base.require(sum(r["bytes"] for r in weights) <= MAX_WEIGHT_BYTES, "vision_weight_cap")
    base.require(
        sum(r["bytes"] for r in rows if r["role"] == "metadata") <= MAX_METADATA_BYTES,
        "vision_metadata_cap",
    )
    for row in rows:
        base.require(
            Path(row["filename"]).name == row["filename"]
            and not row["filename"].endswith(".py")
            and row["bytes"] > 0
            and row["hash_kind"] in ("sha256", "git_blob_sha1")
            and re.fullmatch(
                r"[0-9a-f]{64}" if row["hash_kind"] == "sha256" else r"[0-9a-f]{40}",
                row["expected_hash"],
            ),
            "vision_safe_pinned_file",
        )
    return rows


def runtime_metadata():
    # Distribution metadata only: no torch, transformers, model or processor import.
    code = (
        "import importlib.metadata as m,json,sys;"
        "names=['torch','transformers','Pillow','torchvision'];v={};"
        "\nfor n in names:\n"
        " try:v[n]=m.version(n)\n except m.PackageNotFoundError:v[n]=None\n"
        "print(json.dumps(dict(versions=v,python=list(sys.version_info[:3]),"
        "torch_site=str(m.distribution('torch').locate_file('')))))"
    )
    return json.loads(subprocess.check_output([str(SOURCE_PYTHON), "-I", "-c", code], text=True))


def plan_fields(runtime):
    base.require(
        runtime["python"][:2] == [3, 12]
        and all(runtime["versions"][k] == v for k, v in EXPECTED_VERSIONS.items()),
        "vision_exact_inherited_runtime",
    )
    base.require(
        Path(runtime["torch_site"])
        .resolve()
        .is_relative_to((base.ROOT_DATA / "trusted_data_synthesis/.venv").resolve()),
        "vision_inherited_site",
    )
    rows = manifest()
    return dict(
        status="FILES_PLANNED_DEPENDENCIES_PENDING_NOT_DOWNLOADED_NOT_LOADED",
        repository=REPO,
        revision=REVISION,
        official_metadata_source=f"https://huggingface.co/api/models/{REPO}?blobs=true",
        metadata_observation=dict(
            date="2026-09-27",
            HTTP_status=200,
            response_bytes=5219,
            private=False,
            gated=False,
            license="apache-2.0",
        ),
        model_files=rows,
        dependency_wheels=list(WHEELS),
        inherited_runtime=runtime,
        source_python=str(SOURCE_PYTHON),
        proposed_model_directory=str(RAW / "model" / REVISION),
        proposed_environment_directory=str(RAW / "venv"),
        proposed_environment_kind="system-site-packages venv plus own explicit parent-site .pth",
        weight_bytes=sum(r["bytes"] for r in rows if r["role"] == "weights"),
        metadata_bytes=sum(r["bytes"] for r in rows if r["role"] == "metadata"),
        proposed_maximum_weight_bytes=MAX_WEIGHT_BYTES,
        proposed_maximum_metadata_bytes=MAX_METADATA_BYTES,
        weight_download_authorized=False,
        dependency_install_authorized=False,
        source_build_authorized=False,
        environment_creation_authorized=False,
        network_requests=0,
        model_loads=0,
        GPU_processes=0,
        PDF_opens=0,
        page_renders=0,
        semantic_certificates=0,
        Student_environment_writes=0,
        trust_remote_code=False,
        independence="Separate OpenGVLab checkpoint and local execution from DeepSeek scanner "
        "and Qwen Student, NOT independent model lineage: Qwen3-8B backbone; official card "
        "describes DeepSeek-R1-assisted training rollouts. No semantic independence certificate.",
        load_readiness="PENDING_DEPENDENCIES_AND_RUNTIME_VALIDATION",
        source_build_alternative=dict(
            repository="https://github.com/pytorch/vision",
            tag="v0.22.1",
            commit="59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca",
            status="OFFICIAL_SOURCE_ROUTE_IDENTIFIED_NOT_FETCHED_OR_BUILT",
            pending="Freeze separate CPU build environment and compatible setuptools "
            "providing pkg_resources; current setuptools83 lacks it. No change to Student.",
        ),
    )


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    root = Path(root)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in (SCRIPT, base.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", f"{head}:{name}"], cwd=root),
            "vision_committed_code",
        )
        sources[name] = base.sha(payload)
    plan = base.record(
        PROTOCOL,
        at=base.now(),
        code_commit=head,
        sources=sources,
        **plan_fields(runtime_metadata()),
    )
    base.require(RAW.resolve().is_relative_to(base.RAW.resolve()), "vision_output_root")
    base.write(RAW / "protocol.json", plan)
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), PROTOCOL)
    for name, digest in plan["sources"].items():
        base.require(base.sha(Path(root) / name) == digest, "vision_frozen_code")
    expected = plan_fields(plan["inherited_runtime"])
    base.require(all(plan[key] == value for key, value in expected.items()), "vision_frozen_plan")
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "register", "status"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    if args.command == "plan":
        value = plan_fields(runtime_metadata())
    elif args.command == "register":
        value = register(args.root)
    else:
        value = protocol(args.root)
    base.emit(value)


if __name__ == "__main__":
    main()
