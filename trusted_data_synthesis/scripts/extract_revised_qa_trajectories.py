"""Export frozen revised QA runs without executing models or rewriting responses."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = {
    "task_panel": "qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906",
    "support_exploration": (
        "qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907"
    ),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def extract(output):
    sources = {}

    def read(path):
        raw = path.read_bytes()
        sources[str(path.relative_to(ROOT))] = {"bytes": len(raw), "sha256": digest(raw)}
        return json.loads(raw)

    def verify_manifest(path):
        manifest = read(path)
        for member in manifest["members"]:
            target = path.parent / member["path"]
            raw = target.read_bytes()
            if len(raw) != member["bytes"] or digest(raw) != member["sha256"]:
                raise ValueError(f"Manifest mismatch: {target}")

    trajectories, positive, candidates, summaries = [], [], [], {}
    for cohort, relative in RUNS.items():
        execution = ROOT / "trusted_data_synthesis/artifacts" / relative / "execution"
        analysis = execution / "analysis"
        verify_manifest(analysis / "manifest.json")
        outcomes = read(analysis / "session_outcomes.json")
        outcomes = outcomes["rows"] if isinstance(outcomes, dict) else outcomes
        packages = read(analysis / "session_packages.json")
        package_map = {r["label"]: r for r in packages["rows"]}
        dataset = read(analysis / "supervision_candidates.json")
        rows = dataset["rows"] if isinstance(dataset, dict) else dataset
        session_map = {}
        for outcome in outcomes:
            label = outcome["label"]
            package = package_map[label]
            runtime = execution / "sessions" / label / "runtime"
            verify_manifest(runtime / "manifest.json")
            session = read(runtime / "session.json")
            if session["id"] != package["session_id"]:
                raise ValueError(f"Session mismatch: {cohort}/{label}")
            record = {
                "schema_version": "revised_qa_trajectory_export.v1",
                "cohort": cohort,
                "label": label,
                "source_run": relative,
                "outcome": outcome,
                "package": package,
                "context": read(runtime / "context.json"),
                "protocol": read(runtime / "protocol.json"),
                "registry": read(runtime / "registry.json"),
                "session": session,
            }
            trajectories.append(record)
            if package["positive_eligible"]:
                if not package["complete"] or package["qualification_status"] != "success":
                    raise ValueError(f"Incomplete positive package: {label}")
                positive.append(record)
            session_map[session["id"]] = (record, runtime)
        for candidate in rows:
            record, runtime = session_map[candidate["session_id"]]
            if not record["package"]["positive_eligible"] or not all(
                candidate[k] is True for k in ("admitted", "qualified", "model_origin_verified")
            ):
                raise ValueError("Ineligible supervision candidate")
            turn = candidate["turn_index"]
            event = next(e for e in record["session"]["events"] if e["sequence"] == turn)
            if (
                event["submission"]["id"] != candidate["submission_id"]
                or event["receipt"]["id"] != candidate["receipt_id"]
            ):
                raise ValueError("Candidate event binding mismatch")
            raw = (runtime / "turns" / f"{turn:03d}_response.txt").read_bytes()
            if (
                raw != candidate["target_text"].encode("utf-8")
                or digest(raw) != candidate["target_raw_sha256"]
                or len(raw) != candidate["target_raw_byte_count"]
            ):
                raise ValueError("Original response mismatch")
            candidates.append(
                {
                    "cohort": cohort,
                    "label": record["label"],
                    "source_run": relative,
                    "candidate": candidate,
                }
            )
        expected = {u["candidate_id"] for p in packages["rows"] for u in p["units"]}
        if expected != {c["id"] for c in rows} or len(expected) != len(rows):
            raise ValueError("Package candidate coverage mismatch")
        summaries[cohort] = {
            "sessions": len(outcomes),
            "qualified_sessions": sum(p["positive_eligible"] for p in packages["rows"]),
            "supervision_rows": len(rows),
            "events": sum(
                len(r["session"]["events"]) for r in trajectories if r["cohort"] == cohort
            ),
        }
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, records in [
        ("trajectories.all", trajectories),
        ("trajectories.qualified", positive),
        ("supervision", candidates),
    ]:
        raw = b"".join(
            (json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            for r in records
        )
        name += ".jsonl.gz"
        packed = gzip.compress(raw, mtime=0)
        (output / name).write_bytes(packed)
        if [json.loads(line) for line in gzip.decompress(packed).splitlines()] != records:
            raise ValueError("Export roundtrip mismatch")
        files[name] = {
            "rows": len(records),
            "bytes": len(packed),
            "sha256": digest(packed),
            "uncompressed_bytes": len(raw),
        }
    manifest = {
        "schema_version": "revised_qa_trajectory_export_manifest.v1",
        "cohorts": summaries,
        "files": files,
        "sources": sources,
        "qualification_recomputed": False,
        "new_model_calls": 0,
        "class_weights_assigned": False,
        "validation": [
            "source analysis and runtime manifest member hashes",
            "session and submission/receipt bindings",
            "positive package candidate coverage",
            "exact UTF-8 response bytes and hashes",
            "gzip JSONL roundtrip",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"cohorts": summaries, "files": files}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    extract(parser.parse_args().output)
