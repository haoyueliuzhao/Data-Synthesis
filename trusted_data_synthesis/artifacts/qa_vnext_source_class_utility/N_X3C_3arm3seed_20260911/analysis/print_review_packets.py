"""Read only masked packets; print complete unique text plus every occurrence.

This is a post-hoc viewing aid, not an evaluator. It never reads the identity map,
model, seed, training logs, or private financial reference. Exact repeated public
strings are displayed once with all original indices; no episode is shortened,
no event is removed, and no score or review is written.
"""

import argparse
import copy
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("dev", "confirm"), required=True)
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--last", type=int, required=True)
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1]
    packets = output / "assessment" / args.phase / "public_review_packets"
    for ordinal in range(args.first, args.last + 1):
        rid = f"{args.phase}_{ordinal:03d}"
        packet = json.loads((packets / (rid + ".json")).read_bytes())
        public = packet["public_document"]
        print(json.dumps({
            "review_id": rid, "task_key": packet["task_key"], "question": public["question"],
            "terminal": packet["terminal"], "first_final_index": packet["first_final_index"],
            "raw_final": packet["raw_final"],
            "all_generated_response_count": len(packet["all_generated_public_messages"]),
            "admitted_response_indices": sorted(map(int, packet["raw_messages"])),
        }, ensure_ascii=False))
        groups = {}
        for index, raw in sorted(packet["all_generated_public_messages"].items(),
                                 key=lambda item: int(item[0])):
            groups.setdefault(raw, []).append(int(index))
        for raw, indices in groups.items():
            print(json.dumps({"original_response_indices": indices}, ensure_ascii=False))
            print(raw)
        event_groups = {}
        for event in packet["actual_events"]:
            body = copy.deepcopy(event)
            occurrence = {
                "response_index": body.pop("response_index"),
            }
            # Byte hashes remain in the original packet and frozen audit.
            body.pop("raw_sha256")
            if body["tool_call"] is not None:
                call = body["tool_call"]
                occurrence["call_id"] = call.pop("id")
                occurrence["output_call_id"] = call["output"].pop("call_id")
            key = json.dumps(body, sort_keys=True, ensure_ascii=False)
            event_groups.setdefault(key, []).append(occurrence)
        for body, occurrences in event_groups.items():
            print("ACTUAL_EVENT_OCCURRENCES", json.dumps(occurrences, ensure_ascii=False))
            print("ACTUAL_EVENT_SHARED_BODY", body)
        print("AUDITED_CALCULATIONS", json.dumps(packet["calculations"], ensure_ascii=False))


if __name__ == "__main__":
    main()
