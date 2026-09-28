"""Capture public official DeepSeek documentation; no key or model request."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

URLS = {
    "pricing": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
    "thinking": "https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/",
    "chat": "https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("official snapshot is immutable; choose a new directory")
    bodies, records = {}, []
    with httpx.Client(timeout=40, follow_redirects=True) as client:
        for name, url in URLS.items():
            response = client.get(url)
            response.raise_for_status()
            if response.url.host != "api-docs.deepseek.com":
                raise ValueError("official document redirected outside the official host")
            body = response.content
            bodies[name + ".html"] = body
            records.append(
                dict(
                    name=name,
                    url=url,
                    final_url=str(response.url),
                    status=response.status_code,
                    sha256=hashlib.sha256(body).hexdigest(),
                    bytes=len(body),
                )
            )
    snapshot = dict(
        schema="finqa_probe_official_docs.v1",
        checked_at_utc=datetime.now(timezone.utc).isoformat(),
        documents=records,
        model_requests=0,
        retries=0,
        credentials_used=False,
        observation_method=(
            "official live web reading plus captured original HTML; not an API invoice"
        ),
        model="deepseek-flash",
        model_version_as_documented="DeepSeek-V4.1-Flash",
        CNY_per_million_tokens=dict(
            off_peak=dict(input_cache_hit="0.02", input_cache_miss="1", output="4"),
            peak=dict(input_cache_hit="0.04", input_cache_miss="2", output="8"),
        ),
        peak_hours_description=(
            "Asia/Shanghai Monday-Friday excluding China statutory holidays, "
            "09:00-12:00 and 14:00-18:00; all other hours off-peak"
        ),
        model_context_advertised="1M",
        conservative_input_token_reservation=1048576,
        reservation_size_is_upper_bound_not_independent_tokenizer_measurement=True,
        official_max_output_tokens=393216,
        collection_max_output_tokens=2048,
        collection_thinking={"type": "disabled"},
        billing_estimate_policy="use peak prices at every hour as a conservative upper bound",
        official_usage_fields=[
            "prompt_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
            "completion_tokens",
            "total_tokens",
        ],
        budget_authority="separate run protocol; this public-document capture authorizes no calls",
        budget_not_a_guarantee_of_all_registered_sessions=True,
    )
    raw = (json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    write_immutable_artifact_directory(args.output, {**bodies, "snapshot.json": raw})
    print(
        json.dumps(
            dict(
                path=str(args.output / "snapshot.json"),
                sha256=hashlib.sha256(raw).hexdigest(),
                documents=len(records),
                model_requests=0,
            )
        )
    )


if __name__ == "__main__":
    main()
