"""One finite official-source CPU torchvision build; no VLM or financial images.

Freeze first. Three fixed public artifacts, one environment/build attempt, no
automatic retry. The denied prebuilt torchvision wheel is never requested.
"""

import argparse
import hashlib
import json
import os
import shutil
import signal
import ssl
import subprocess
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

import provision_cross_market_vision_pilot_20260927 as parent

base = parent.base
SCRIPT = "trusted_data_synthesis/scripts/build_cross_market_vision_environment_20260927.py"
RAW = base.RAW / "original_evidence_revision_02" / "vision_source_build_01"
KIND = "cross_market_vision_source_build_protocol"
COMPLETE = "cross_market_vision_source_build_completed"
COMMIT = "59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca"
VERSION = "0.22.1+localcpu"
MAX_ARCHIVE_BYTES = 256 * 2**20
MAX_EXTRACTED_BYTES = 2 * 2**30
MAX_ENTRIES = 20000
MAX_WHEEL_BYTES = 256 * 2**20
BUILD_TIMEOUT = 1800
MIN_FREE_BYTES = 20 * 2**30
BUILD_FLAGS = dict(
    BUILD_VERSION=VERSION,
    CUDA_VISIBLE_DEVICES="",
    FORCE_CUDA="0",
    FORCE_MPS="0",
    MAX_JOBS="8",
    TORCHVISION_USE_PNG="0",
    TORCHVISION_USE_JPEG="0",
    TORCHVISION_USE_WEBP="0",
    TORCHVISION_USE_NVJPEG="0",
    TORCHVISION_USE_VIDEO_CODEC="0",
    TORCHVISION_USE_FFMPEG="0",
)
ARTIFACTS = (
    dict(
        key="source",
        filename=f"vision-{COMMIT}.tar.gz",
        url=f"https://github.com/pytorch/vision/archive/{COMMIT}.tar.gz",
        hosts=["github.com", "codeload.github.com"],
        bytes=None,
        maximum_bytes=MAX_ARCHIVE_BYTES,
        sha256=None,
    ),
    dict(
        key="pillow",
        filename=parent.WHEELS[0]["filename"],
        url="https://files.pythonhosted.org/packages/84/21/"
        "a35af28dcc61f37ed850a2d64c65c701321dfbf25085e469d5559360cbbf/"
        "pillow-12.3.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl",
        hosts=["files.pythonhosted.org"],
        bytes=6940830,
        maximum_bytes=6940830,
        sha256="78cb2c6865a35ab8ff8b75fd122f6033b92a62c82801110e48ddd6c936a45d91",
    ),
    dict(
        key="setuptools",
        filename="setuptools-80.9.0-py3-none-any.whl",
        url="https://files.pythonhosted.org/packages/a3/dc/"
        "17031897dae0efacfea57dfd3a82fdd2a2aeb58e0ff71b77b87e44edc772/"
        "setuptools-80.9.0-py3-none-any.whl",
        hosts=["files.pythonhosted.org"],
        bytes=1201486,
        maximum_bytes=1201486,
        sha256="062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922",
    ),
)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "vision_build_output_root")
    base.write(path, value)


def ref(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=base.sha(path))


def checked_ref(value):
    path = Path(value["path"])
    base.require(
        path.is_file() and not path.is_symlink() and ref(path) == value,
        "vision_build_saved_reference",
    )
    return path


def metadata(python):
    names = ["torch", "transformers", "numpy", "wheel", "setuptools", "Pillow", "torchvision"]
    code = (
        "import importlib.metadata as m,json,sys;v={};"
        f"\nfor n in {names!r}:\n"
        " try:v[n]=dict(version=m.version(n),site=str(m.distribution(n).locate_file('')))\n"
        " except m.PackageNotFoundError:v[n]=None\n"
        "print(json.dumps(dict(python=list(sys.version_info[:3]),packages=v)))"
    )
    return json.loads(
        subprocess.check_output([str(python), "-I", "-B", "-c", code], text=True, timeout=30)
    )


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    prior = parent.protocol(root)
    root = Path(root)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(prior["sources"])
    payload = (root / SCRIPT).read_bytes()
    base.require(
        payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "vision_build_committed_code",
    )
    sources[SCRIPT] = base.sha(payload)
    runtime = metadata(parent.SOURCE_PYTHON)
    base.require(
        runtime["python"][:2] == [3, 12]
        and all(runtime["packages"][k]["version"] == v for k, v in parent.EXPECTED_VERSIONS.items())
        and runtime["packages"]["numpy"]["version"] == "2.5.1"
        and runtime["packages"]["wheel"]["version"] == "0.47.0",
        "vision_build_fixed_inherited_runtime",
    )
    plan = base.record(
        KIND,
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_protocol=ref(parent.RAW / "protocol.json"),
        parent_protocol_id=prior["id"],
        artifacts=list(ARTIFACTS),
        original_source_commit=COMMIT,
        original_source_archive_expected_sha256=None,
        archive_integrity="Pinned official HTTPS commit archive; record received SHA256 before "
        "extraction. No pre-existing archive SHA256 or signed-build claim.",
        runtime=runtime,
        source_python=str(parent.SOURCE_PYTHON),
        inherited_site=prior["inherited_runtime"]["torch_site"],
        build_flags=BUILD_FLAGS,
        expected_local_version=VERSION,
        system_site_packages=True,
        maximum_artifact_attempts=3,
        maximum_attempts_per_artifact=1,
        maximum_redirects_per_artifact=2,
        maximum_total_HTTP_requests=9,
        maximum_archive_bytes=MAX_ARCHIVE_BYTES,
        maximum_extracted_bytes=MAX_EXTRACTED_BYTES,
        maximum_archive_entries=MAX_ENTRIES,
        maximum_produced_wheel_bytes=MAX_WHEEL_BYTES,
        maximum_environment_build_attempts=1,
        maximum_build_seconds=BUILD_TIMEOUT,
        minimum_initial_free_bytes=MIN_FREE_BYTES,
        maximum_artifact_seconds=600,
        socket_timeout_seconds=60,
        maximum_requested_CPU_jobs=8,
        ninja_install=False,
        parallelism_note="MAX_JOBS=8 is an upper request, not proof of eight workers; "
        "without ninja the standard distutils backend may be serial.",
        authorized_operations=[
            "3_fixed_artifact_GETs",
            "isolated_venv",
            "local_no_deps_install",
            "one_CPU_torchvision_build",
            "synthetic_CPU_resize_smoke",
        ],
        automatic_retries=0,
        proxy_changes=0,
        denied_wheel_requests=0,
        model_weight_downloads=0,
        model_loads=0,
        GPU_processes=0,
        PDF_opens=0,
        actual_image_reads=0,
        semantic_certificates=0,
        Student_environment_writes=0,
    )
    save(RAW / "protocol.json", plan)
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), KIND)
    for name, digest in plan["sources"].items():
        base.require(base.sha(Path(root) / name) == digest, "vision_build_frozen_code")
    checked_ref(plan["parent_protocol"])
    base.require(
        plan["artifacts"] == list(ARTIFACTS)
        and plan["build_flags"] == BUILD_FLAGS
        and plan["maximum_artifact_attempts"] == 3
        and plan["maximum_environment_build_attempts"] == 1,
        "vision_build_fixed_scope",
    )
    return plan


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def allowed_url(url, item):
    parsed = urllib.parse.urlsplit(url)
    base.require(
        parsed.scheme == "https"
        and parsed.hostname in item["hosts"]
        and parsed.port in (None, 443)
        and parsed.username is None
        and parsed.password is None,
        "vision_build_official_URL",
    )
    return parsed


def acquire(plan, item):
    destination = RAW / "downloads" / item["filename"]
    destination.parent.mkdir(exist_ok=True)
    base.require(not destination.exists(), "vision_build_no_artifact_overwrite")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    url, started = item["url"], time.monotonic()
    for hop in range(3):
        parsed = allowed_url(url, item)
        request_path = RAW / "requests" / f"{item['key']}.{hop}.json"
        save(
            request_path,
            base.record(
                "cross_market_vision_source_request",
                at=base.now(),
                protocol_id=plan["id"],
                artifact_key=item["key"],
                request_number=hop + 1,
                method="GET",
                host=parsed.hostname,
                URL_sha256=base.sha(url),
            ),
        )
        try:
            response = opener.open(
                urllib.request.Request(
                    url, headers={"User-Agent": "CrossMarket-OfficialSourceBuild/1.0"}
                ),
                timeout=60,
            )
        except urllib.error.HTTPError as error:
            save(
                RAW / "responses" / f"{item['key']}.{hop}.json",
                base.record(
                    "cross_market_vision_source_HTTP_response",
                    at=base.now(),
                    request=ref(request_path),
                    HTTP_status=error.code,
                ),
            )
            target = error.headers.get("Location")
            error.close()
            if error.code not in (301, 302, 303, 307, 308) or hop == 2:
                raise
            base.require(bool(target), "vision_build_redirect_location")
            url = urllib.parse.urljoin(url, target)
            continue
        partial = destination.with_name(destination.name + ".partial")
        digest, count = hashlib.sha256(), 0
        with response, partial.open("xb") as stream:
            base.require(response.status == 200, "vision_build_HTTP_200")
            while True:
                chunk = response.read(min(2**20, item["maximum_bytes"] - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                base.require(count <= item["maximum_bytes"], "vision_build_download_byte_cap")
                base.require(time.monotonic() - started <= 600, "vision_build_download_time_cap")
                stream.write(chunk)
                digest.update(chunk)
            base.require(
                count > 0 and (item["bytes"] is None or count == item["bytes"]),
                "vision_build_download_exact_size",
            )
            base.require(
                item["sha256"] is None or digest.hexdigest() == item["sha256"],
                "vision_build_download_official_hash",
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.link(partial, destination)
        partial.unlink()
        receipt = base.record(
            "cross_market_vision_source_artifact",
            at=base.now(),
            protocol_id=plan["id"],
            artifact=item,
            HTTP_status=200,
            HTTP_requests=hop + 1,
            actual_file=dict(path=str(destination), bytes=count, sha256=digest.hexdigest()),
            expected_digest_verified=item["sha256"] is not None,
            status="RECEIVED_NOT_EXECUTED",
            seconds=round(time.monotonic() - started, 3),
        )
        # In particular, source archive hash is durably saved BEFORE extraction.
        save(RAW / "receipts" / (item["key"] + ".json"), receipt)
        return receipt
    raise AssertionError("finite redirect loop")


def safe_extract(archive, destination):
    base.require(not destination.exists(), "vision_build_new_extract_directory")
    destination.mkdir()
    prefix, seen, count, size = "vision-" + COMMIT, set(), 0, 0
    with tarfile.open(archive, mode="r|gz") as source:
        for member in source:
            count += 1
            name = PurePosixPath(member.name)
            base.require(count <= MAX_ENTRIES, "vision_build_archive_entry_cap")
            base.require(
                not name.is_absolute()
                and name.parts
                and name.parts[0] == prefix
                and ".." not in name.parts
                and "\\" not in member.name
                and len(member.name) <= 1024
                and member.name not in seen,
                "vision_build_safe_archive_path",
            )
            base.require(member.isdir() or member.isfile(), "vision_build_no_archive_links_devices")
            seen.add(member.name)
            target = destination.joinpath(*name.parts)
            base.require(
                target.resolve().is_relative_to(destination.resolve()),
                "vision_build_confined_extract",
            )
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            size += member.size
            base.require(
                0 <= member.size and size <= MAX_EXTRACTED_BYTES,
                "vision_build_archive_expansion_cap",
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            source_file = source.extractfile(member)
            base.require(source_file is not None, "vision_build_regular_archive_member")
            with source_file, target.open("xb") as output:
                remaining = member.size
                while remaining:
                    chunk = source_file.read(min(2**20, remaining))
                    base.require(bool(chunk), "vision_build_complete_archive_member")
                    output.write(chunk)
                    remaining -= len(chunk)
    root = destination / prefix
    base.require(
        (root / "setup.py").is_file() and (root / "version.txt").is_file(),
        "vision_build_expected_source_root",
    )
    return root, dict(entries=count, extracted_file_bytes=size, original_commit=COMMIT)


def child_environment(source_root):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("PIP_", "GIT_")) and k not in ("PYTHONPATH", "PYTHONHOME")
    }
    for name in ("tmp", "pip_cache", "hf_cache", "torch_cache", "xdg_cache", "extensions"):
        (RAW / name).mkdir(exist_ok=True)
    env.update(BUILD_FLAGS)
    env.update(
        TMPDIR=str(RAW / "tmp"),
        PIP_CACHE_DIR=str(RAW / "pip_cache"),
        HF_HOME=str(RAW / "hf_cache"),
        TORCH_HOME=str(RAW / "torch_cache"),
        XDG_CACHE_HOME=str(RAW / "xdg_cache"),
        TORCH_EXTENSIONS_DIR=str(RAW / "extensions"),
        PIP_CONFIG_FILE=os.devnull,
        PIP_NO_INDEX="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        GIT_CEILING_DIRECTORIES=str(source_root.parent),
    )
    return env


def command(args, *, cwd, env, label, timeout):
    log = RAW / "logs" / (label + ".log")
    log.parent.mkdir(exist_ok=True)
    base.emit(dict(event="vision_source_build_stage", stage=label))
    with log.open("xb") as stream:
        process = subprocess.Popen(
            args, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise ValueError("cross_market.vision_build_subprocess_timeout") from None
    base.require(code == 0, "vision_build_subprocess_failed_" + label)
    return ref(log)


def create_environment(plan, source_root, env):
    target = RAW / "venv"
    base.require(not target.exists(), "vision_build_no_environment_overwrite")
    command(
        [plan["source_python"], "-I", "-B", "-m", "venv", "--system-site-packages", str(target)],
        cwd=RAW,
        env=env,
        label="create_environment",
        timeout=180,
    )
    site = target / "lib/python3.12/site-packages"
    with (site / "cross_market_inherited_runtime.pth").open("x") as stream:
        stream.write(plan["inherited_site"] + "\n")
    python = target / "bin/python"
    env["PATH"] = str(target / "bin") + os.pathsep + env.get("PATH", "")
    wheels = [RAW / "downloads" / item["filename"] for item in ARTIFACTS[1:]]
    pip_install(python, wheels, env, label="install_fixed_build_dependencies")
    current = metadata(python)
    for name in ("torch", "transformers", "numpy", "wheel"):
        base.require(
            current["packages"][name] == plan["runtime"]["packages"][name],
            "vision_build_inherited_package_preserved",
        )
    for name, version in (("setuptools", "80.9.0"), ("Pillow", "12.3.0")):
        package = current["packages"][name]
        base.require(
            package["version"] == version
            and Path(package["site"]).resolve().is_relative_to(target.resolve()),
            "vision_build_local_dependencies",
        )
    return python


def pip_install(python, wheels, env, *, label):
    return command(
        [
            str(python),
            "-I",
            "-B",
            "-m",
            "pip",
            "--disable-pip-version-check",
            "install",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--no-cache-dir",
            "--ignore-installed",
            *map(str, wheels),
        ],
        cwd=RAW,
        env=env,
        label=label,
        timeout=180,
    )


SMOKE = """
import json
import torch, torchvision, PIL
from PIL import Image
from torchvision.transforms.v2 import functional as F
assert torch.__version__ == '2.7.1+cu128'
assert torchvision.__version__ == '0.22.1+localcpu'
assert PIL.__version__ == '12.3.0'
assert torchvision.extension._has_ops()
image = Image.new('RGB', (10, 8), (13, 27, 41))
out = F.resize(image, [4, 5])
tensor = torch.zeros((3, 8, 10), dtype=torch.float32, device='cpu')
resized = F.resize(tensor, [4, 5])
assert out.size == (5, 4) and tuple(resized.shape) == (3, 4, 5)
assert resized.device.type == 'cpu'
print('VISION_BUILD_SMOKE=' + json.dumps(dict(
    torch=torch.__version__, torchvision=torchvision.__version__, Pillow=PIL.__version__,
    native_ops_loaded=True, PIL_output_size=list(out.size), tensor_shape=list(resized.shape),
    tensor_device=str(resized.device), synthetic_images_only=True,
    source_git_version=torchvision.version.git_version)))
"""


def failure(error):
    value = dict(exception_type=type(error).__name__)
    if isinstance(error, urllib.error.HTTPError):
        value["HTTP_status"] = error.code
    reason = getattr(error, "reason", error)
    value["reason_type"] = type(reason).__name__
    if isinstance(getattr(reason, "errno", None), int):
        value["errno"] = reason.errno
    if isinstance(error, ValueError) and str(error).startswith("cross_market.vision_build_"):
        value["guard"] = str(error)
    return value  # Never repr HTTP errors, signed URLs or inherited environment.


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "run.lock"):
        if (RAW / "summary.json").exists():
            result = base.checked(base.read(RAW / "summary.json"), COMPLETE)
            base.require(result["protocol_id"] == plan["id"], "vision_build_completion_identity")
            if result["status"] == "CPU_VISION_ENVIRONMENT_READY_NOT_VLM_VALIDATED":
                checked_ref(result["produced_wheel"])
            return result
        base.require(not (RAW / "attempt.json").exists(), "vision_build_reserved_no_retry")
        base.require(
            shutil.disk_usage(RAW).free >= MIN_FREE_BYTES, "vision_build_initial_disk_headroom"
        )
        base.require(
            metadata(parent.SOURCE_PYTHON) == plan["runtime"],
            "vision_build_parent_before_unchanged",
        )
        save(
            RAW / "attempt.json",
            base.record(
                "cross_market_vision_source_build_attempt",
                at=base.now(),
                protocol_id=plan["id"],
                attempt=1,
                reserved_artifact_attempts=3,
                reserved_build_attempts=1,
            ),
        )
        fields = {}
        started = time.monotonic()
        try:
            receipts = [acquire(plan, item) for item in ARTIFACTS]
            fields["artifact_receipts"] = receipts
            # Source receipt above is durable before any archive member is processed.
            source_root, inventory = safe_extract(
                Path(receipts[0]["actual_file"]["path"]), RAW / "source"
            )
            fields["source_inventory"] = inventory
            env = child_environment(source_root)
            python = create_environment(plan, source_root, env)
            fields["build_log"] = command(
                [str(python), "-I", "-B", "setup.py", "bdist_wheel"],
                cwd=source_root,
                env=env,
                label="build_CPU_torchvision",
                timeout=BUILD_TIMEOUT,
            )
            wheels = list((source_root / "dist").glob("*.whl"))
            base.require(
                len(wheels) == 1
                and wheels[0].name.startswith("torchvision-0.22.1+localcpu-")
                and not wheels[0].is_symlink()
                and 0 < wheels[0].stat().st_size <= MAX_WHEEL_BYTES,
                "vision_build_one_bounded_local_wheel",
            )
            fields["produced_wheel"] = ref(wheels[0])
            save(
                RAW / "built_wheel.json",
                base.record(
                    "cross_market_vision_locally_built_wheel",
                    at=base.now(),
                    protocol_id=plan["id"],
                    source_receipt=ref(RAW / "receipts/source.json"),
                    wheel=fields["produced_wheel"],
                    build_flags=BUILD_FLAGS,
                ),
            )
            pip_install(python, wheels, env, label="install_local_CPU_torchvision")
            fields["smoke_log"] = command(
                [str(python), "-I", "-B", "-c", SMOKE],
                cwd=RAW,
                env=env,
                label="synthetic_CPU_smoke",
                timeout=120,
            )
            lines = Path(fields["smoke_log"]["path"]).read_text().splitlines()
            values = [
                json.loads(line.split("=", 1)[1])
                for line in lines
                if line.startswith("VISION_BUILD_SMOKE=")
            ]
            base.require(len(values) == 1, "vision_build_one_smoke_receipt")
            fields.update(
                smoke=values[0],
                prepared_runtime=metadata(python),
                environment_python=str(python),
                status="CPU_VISION_ENVIRONMENT_READY_NOT_VLM_VALIDATED",
            )
        except Exception as error:
            fields.update(status="SOURCE_BUILD_FAILED_NO_AUTOMATIC_RETRY", error=failure(error))
        unchanged = metadata(parent.SOURCE_PYTHON) == plan["runtime"]
        if not unchanged:
            fields.update(status="PARENT_RUNTIME_CHANGE_REQUIRES_INVESTIGATION")
        result = base.record(
            COMPLETE,
            at=base.now(),
            protocol_id=plan["id"],
            seconds=round(time.monotonic() - started, 3),
            parent_runtime_unchanged=unchanged,
            reserved_environment_build_attempts=1,
            HTTP_requests=len(list((RAW / "requests").glob("*.json"))),
            model_weight_downloads=0,
            model_loads=0,
            GPU_processes=0,
            actual_image_reads=0,
            semantic_certificates=0,
            **fields,
        )
        save(RAW / "summary.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("register", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    if args.command == "register":
        value = register(args.root)
    elif args.command == "run":
        value = run(args.root)
    else:
        value = protocol(args.root)
    base.emit(value)


if __name__ == "__main__":
    main()
