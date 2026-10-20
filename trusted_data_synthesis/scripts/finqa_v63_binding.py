"""Pure bindings for the separately registered balanced feedback repetition.

No model, device, process signal, cron change or scientific write occurs on
import. Historical sources and results are read-only inputs, never a resume
target. All prospective writes belong to ROOT.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V18 = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01"
ROOT = V18 / "v63_balanced_feedback_repetition_01"
OLD_ROOT = V18 / "v54_feedback_temperature_01/automatic_recovery_01"
OLD_PROTOCOL_ID = "53e084012b25dc34cc9a073cb53a1a3bf5d1dc7c4547937cd39e87e4d4be75af"
OLD_IMPLEMENTATION_ID = "e415b937f644b2afde65c1940ef0d0a7f9c0dca03d58d1079ab1e7253132e5e7"
OLD_CLOSEOUT_ID = "9eb85d60c1f25a1dc5f759970aa6ae7c82619284350a07198ac737488871fef7"
USER_AUDIT = Path("/home/zhuxinrui/.codex/attachments/67758c20-6aad-48a8-8052-7d2eb0992567/已粘贴的文本.txt")
PYTHON = REPO / "trusted_data_synthesis/.venv/bin/python"
SEEDS = (137, 251, 389)
ARMS = ("C1", "C05")
TEMPERATURES = {"C1": 1.0, "C05": 0.5}
BATCH = 1
DRAW_SEEDS = (101, 103)
EVALUATION_DRAW_SEEDS = (11, 29)
OWNER_UID = 1004
MAX_WORKERS = 6
_SCIENTIFIC_PATHS = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 ** 2), b""):
            value.update(chunk)
    return value.hexdigest()


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
            "immutable record identity changed: " + str(path))
    return value


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path))


def entry(path):
    path = Path(path).resolve()
    value = checked(path)
    return dict(path=str(path), id=value["id"], sha256=sha(path))


def read_ref(reference):
    path = Path(reference["path"])
    require(sha(path) == reference["sha256"], "bound file bytes changed: " + str(path))
    value = checked(path)
    require("id" not in reference or value["id"] == reference["id"],
            "bound record identity changed")
    return value


def publish(path, body):
    """Immutable, fsynced JSON publication; no historical directory writes."""
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT.resolve()),
            "V63 cannot publish outside its independent experiment root")
    require(not path.is_symlink(), "symlink artifact rejected")
    body = {k: v for k, v in body.items() if k != "id"}
    value = {**body, "id": digest(body)}
    if path.exists():
        require(checked(path) == value, "existing immutable V63 record differs")
        return value
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".v63-record-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return value


def install_scientific_paths():
    """Select only the old byte-frozen math, before any science imports.

    A workspace preparation consumes the existing 96-file bundle. Production
    consumes its byte-identical copies in the new committed V63 bundle. This
    does not change any historical module or claim a new scientific launch.
    """
    global _SCIENTIFIC_PATHS
    if _SCIENTIFIC_PATHS is not None:
        return _SCIENTIFIC_PATHS
    old = checked(OLD_ROOT / "implementation/record.json")
    require(old["id"] == OLD_IMPLEMENTATION_ID and len(old["sha256"]) == 96,
            "the original completed experiment implementation changed")
    here = Path(__file__).resolve().parent
    frozen = here == ROOT / "implementation"
    science = here if frozen else OLD_ROOT / "implementation"
    if frozen:
        manifest = checked(here / "record.json")
        require(all(manifest["sha256"].get(name) == expected
                    for name, expected in old["sha256"].items()),
                "the original 96 files must be byte-identical")
    source = Path(old["frozen_source_root"]).resolve()
    for path in (science, source):
        text = str(path)
        if text in sys.path:
            sys.path.remove(text)
        sys.path.insert(0, text)
    for name, module in tuple(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if name + ".py" in old["sha256"] and origin:
            require(Path(origin).resolve() == science / (name + ".py"),
                    "scientific module imported before the frozen path: " + name)
        if (name == "trusted_synthesis" or name.startswith("trusted_synthesis.")) and origin:
            require(Path(origin).resolve().is_relative_to(source),
                    "workspace scientific package imported before the frozen source")
    _SCIENTIFIC_PATHS = dict(scientific_scripts=str(science),
                            frozen_source_root=str(source), production_bundle=frozen)
    return _SCIENTIFIC_PATHS


def old_module(name):
    install_scientific_paths()
    require(name.startswith("finqa_") and not name.startswith("finqa_v63_"),
            "old_module requires an explicitly historical scientific module")
    return importlib.import_module(name)


def coordinate(seed, arm):
    require(seed in SEEDS and arm in ARMS, "unregistered new feedback condition")
    return f"seed{seed}/{arm}"
