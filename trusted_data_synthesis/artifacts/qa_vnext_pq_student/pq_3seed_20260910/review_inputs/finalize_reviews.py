"""Combine the explicit offline reviews, prequalify all 84, then finalize once."""

import json
from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_pq_student import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import read_json, sha


def main():
    root = Path(__file__).resolve().parents[5]
    output, prep, _, targets = evaluate._prepared(root)
    evaluate.manifest(output / "assessment")
    assessment = read_json(output / "assessment/report.json")
    destination = output / "review_inputs/combined_reviews.json"
    assert not destination.exists() and not (output / "closeout").exists()
    reviews, provenance = {}, []
    for name, expected in (("reviewer_root", 12), ("reviewer_a", 36), ("reviewer_b", 36)):
        path = output / "review_inputs" / (name + ".json")
        submitted = read_json(path)
        part = submitted["reviews"]
        assert len(part) == expected and not (set(part) & set(reviews))
        reviews.update(part)
        script = path.with_suffix(".py")
        provenance.append({
            "path": path.relative_to(output).as_posix(),
            "sha256": sha(path.read_bytes()),
            "script_sha256": sha(script.read_bytes()),
            "reviews": len(part),
        })
    assert len(assessment["rows"]) == 84
    assert set(reviews) == {row["key"] for row in assessment["rows"]}
    grades, failures = [], {}
    for row in assessment["rows"]:
        key, task = row["key"], row["task_key"]
        try:
            grades.append(evaluate.qualify(
                read_json(output / f"assessment/audits/{key}.json"),
                reviews[key],
                read_json(prep / f"public/{task}.json"),
                targets[task],
            ))
        except Exception as error:
            failures[key] = f"{type(error).__name__}: {error}"
    assert not failures, failures
    assert len(grades) == 84
    submitted = {
        "reviews": reviews,
        "provenance": provenance,
        "combination_script_sha256": sha(Path(__file__).read_bytes()),
        "scope": (
            "Post-generation Codex root/subagent finite semantic review, not independent "
            "human expert or blind review. Full frozen policy unchanged; disputed source "
            "and unit cases resolved from actual pre-call/source/Final evidence. All 84 "
            "reviews prequalified in memory before creating closeout."
        ),
        "prequalification": {
            "sessions": len(grades),
            "exceptions": {},
            "answer_statuses": dict(Counter(g["task_answer_status"] for g in grades)),
        },
    }
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(submitted, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    digest = sha(destination.read_bytes())
    assert sha(destination.read_bytes()) == digest
    result = evaluate.finalize(root, destination)
    assert sha(destination.read_bytes()) == digest
    print(result["id"])
    print(json.dumps(result["by_variant"], ensure_ascii=False, indent=2))
    print(json.dumps(result["paired_seed_differences"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
