"""Immutable records and a zero-model, new-output-only execution boundary."""

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

BASELINE = "7127abf55ba09e3f66278366a01a14752c9766dc"
OLD = "trusted_data_synthesis/artifacts/qa_vnext_source_class_utility/N_X3C_3arm3seed_20260911"
PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_target_binding"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_target_binding/fixed_36targets_18cases_20260911"
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_target_binding.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_target_binding.py"
AUDIT = "/home/zhuxinrui/.codex/attachments/27f8a1c3-c19d-4da9-9d8c-65d6188ff2c2/pasted-text.txt"
AUDIT_SHA = "f94b8e10ee9e16108a3ec91d4f0ed1086cf429f907d9dbc5e7f473ef215e61e4"
TASKS = tuple(f"D{i:02}" for i in range(1, 13)) + tuple(f"C{i:02}" for i in range(1, 25))
CASE_TASKS = ("C04", "C08", "C09")
SEEDS = (11, 29, 47)
CASE_KEYS = tuple(
    (task, arm, seed) for task in CASE_TASKS for arm in ("pi0", "minus_D") for seed in SEEDS
)
STATUSES = frozenset({"PASS", "FAIL", "UNDETERMINED", "NOT_ESTABLISHED"})
ALIGNMENTS = frozenset(
    {"ALIGNED", "PUBLIC_UNDERSPECIFIED", "PRIVATE_MISMATCH", "NEED_SOURCE_CHECK"}
)
ZERO_RESOURCES = {
    "Teacher_sessions": 0,
    "Teacher_generation_requests": 0,
    "Student_generation_requests": 0,
    "Student_sessions": 0,
    "training_runs": 0,
    "tokenizer_calls": 0,
    "NLL_evaluations": 0,
    "B0_or_same_task_greedy": 0,
    "historical_tool_replays": 0,
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def record(kind, **fields):
    body = {"schema_version": "target_binding_audit.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def read_json(path):
    return json.loads(Path(path).read_bytes())


def reference(root, relative):
    relative = str(relative)
    path = Path(root) / relative
    require(path.is_file() and not path.is_symlink(), "reference.regular_file")
    require(path.resolve().is_relative_to(Path(root).resolve()), "reference.within_repository")
    raw = path.read_bytes()
    return {"path": relative, "bytes": len(raw), "sha256": sha(raw)}


def read_bound(root, ref):
    require(reference(root, ref["path"]) == ref, "reference.unchanged")
    return read_json(Path(root) / ref["path"])


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        *[":(exclude)" + p for p in (PACKAGE, OUTPUT, DOCUMENT, TEST)],
    ]
    require(
        not subprocess.check_output(
            ["git", "diff", "--name-only", BASELINE, "--", *paths], cwd=root
        ),
        "history.closed_experiment_unchanged",
    )
    require(
        not subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=root),
        "history.no_uncommitted_historical_changes",
    )
    return {"baseline": BASELINE, "historical_files_unchanged": True}


def seal(root, phase, payloads, *, report_name="report.json"):
    directory = Path(root) / OUTPUT / phase
    require(not directory.exists(), "phase.write_once")
    require(
        report_name in payloads and "manifest.json" not in payloads, "phase.report_and_manifest"
    )
    for name in payloads:
        p = Path(name)
        require(not p.is_absolute() and ".." not in p.parts, "phase.relative_output_name")
    directory.mkdir(parents=True)
    refs = []
    for name, value in payloads.items():
        raw = value if isinstance(value, bytes) else encode(value)
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        refs.append(reference(root, target.relative_to(root)))
    report = payloads[report_name]
    manifest = record(
        "phase_manifest",
        phase=phase,
        files=refs,
        report_id=report.get("id") if isinstance(report, dict) else None,
    )
    with (directory / "manifest.json").open("xb") as handle:
        handle.write(encode(manifest))
        handle.flush()
        os.fsync(handle.fileno())
    return manifest


def read_phase(root, phase):
    directory = Path(root) / OUTPUT / phase
    manifest = read_json(directory / "manifest.json")
    for ref in manifest["files"]:
        require(reference(root, ref["path"]) == ref, "phase.sealed_file_unchanged")
    report = read_json(directory / "report.json")
    require(report["id"] == manifest["report_id"], "phase.report_binding")
    return report, manifest


def implementation_references(root):
    paths = sorted((Path(root) / PACKAGE).glob("*.py"))
    require(
        {p.name for p in paths}
        == {
            "__init__.py",
            "core.py",
            "policy.py",
            "ledger.py",
            "failure_structure.py",
            "cases.py",
            "stage.py",
        },
        "implementation.complete_before_ledger_freeze",
    )
    return [reference(root, path.relative_to(root)) for path in paths] + [reference(root, TEST)]


def require_frozen_ledger(root):
    report, manifest = read_phase(root, "ledger")
    for ref in report["implementation"]:
        require(reference(root, ref["path"]) == ref, "ledger.frozen_implementation")
    return report, manifest


class ZeroModelGuard:
    """Process-local instrumentation, not a claim of OS-level isolation."""

    forbidden_imports = frozenset(
        {
            "torch",
            "transformers",
            "tokenizers",
            "peft",
            "accelerate",
            "vllm",
            "openai",
            "httpx",
            "requests",
            "numpy",
        }
    )

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.output = (self.root / OUTPUT).resolve()
        self.active = False
        self.counts = Counter()

    def _event(self, event, args):
        if not self.active:
            return
        if event == "import" and str(args[0]).split(".", 1)[0] in self.forbidden_imports:
            self.counts["blocked_model_or_client_imports"] += 1
            raise PermissionError("zero_model.forbidden_import")
        if event.startswith("socket.") or event in {
            "subprocess.Popen",
            "os.system",
            "os.posix_spawn",
        }:
            self.counts["blocked_network_or_process_events"] += 1
            raise PermissionError("zero_model.no_network_or_child_process")
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.name == ".env":
                self.counts["blocked_credential_reads"] += 1
                raise PermissionError("zero_model.no_credentials")
            mode = args[1] or ""
            flags = args[2] or 0
            writing = any(c in str(mode) for c in "wax+") or bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            )
            if writing and not path.is_relative_to(self.output):
                self.counts["blocked_historical_or_external_writes"] += 1
                raise PermissionError("zero_model.new_output_only")
        if event in {
            "os.mkdir",
            "os.remove",
            "os.rmdir",
            "os.rename",
            "os.link",
            "os.symlink",
            "os.truncate",
        }:
            targets = args[:2] if event in {"os.rename", "os.link", "os.symlink"} else args[:1]
            for target in targets:
                if isinstance(target, (str, bytes, os.PathLike)):
                    path = Path(os.fsdecode(target)).resolve()
                    new_category_parent = event == "os.mkdir" and path == self.output.parent
                    if not path.is_relative_to(self.output) and not new_category_parent:
                        self.counts["blocked_historical_or_external_writes"] += 1
                        raise PermissionError("zero_model.new_output_only")

    def __enter__(self):
        require(
            not any(name.split(".", 1)[0] in self.forbidden_imports for name in sys.modules),
            "zero_model.no_preloaded_model_libraries",
        )
        sys.addaudithook(self._event)
        self.active = True
        return self

    def __exit__(self, *_):
        self.active = False

    def receipt(self):
        return {
            "scope": "process-local Python audit hooks; not absolute OS isolation",
            "events": dict(self.counts),
            "new_resources": dict(ZERO_RESOURCES),
        }
