"""Post-generation review of all twelve no-Final baseline sessions; no model calls."""

import json
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_pq_student import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import OUTPUT, read_json


def main():
    root = Path(__file__).resolve().parents[5]
    output, prep, registrations, targets = evaluate._prepared(root)
    assert output == root / OUTPUT
    evaluate.manifest(output / "assessment")
    reviews = {}
    for registration in registrations:
        task = registration["task_key"]
        key = "B0/" + task
        audit = read_json(output / "assessment/audits" / (key + ".json"))
        public = read_json(prep / "public" / (task + ".json"))
        assert audit["first_final_index"] is None
        assert audit["tool_calls"] == 0 and not audit["calculations"]
        review = evaluate.review_template(audit, public, targets[task])
        review["author"] = "Codex root offline semantic-review agent; not an independent human expert"
        review["publication"]["explanation"] = (
            "No protocol-valid first Final was delivered. Do not extract an answer from "
            "unadmitted prose or protocol-invalid assistant messages."
        )
        review["calculation"]["explanation"] = "No actual successful calculate call exists."
        for field in evaluate.FIELDS:
            review[field]["explanation"] = (
                "Not established for a completed task: no admitted Final and no actual tool "
                "execution. This is not a finding of incorrect financial arithmetic."
            )
        grade = evaluate.qualify(audit, review, public, targets[task])
        assert grade["task_answer_status"] == "UNDETERMINED"
        assert grade["delivery_status"] == "NO_FINAL"
        assert grade["trace_status"] == "NOT_ESTABLISHED"
        assert not grade["complete_verifiable_trajectory"]
        reviews[key] = review
    path = Path(__file__).with_suffix(".json")
    with path.open("x", encoding="utf-8") as handle:
        json.dump({"reviews": reviews}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print("baseline reviews qualified", len(reviews), path)


if __name__ == "__main__":
    main()
