"""Bounded official SEC source acquisition and frozen new-180 public panel build."""

# ruff: noqa: E501 -- explicit source-selection and acquisition contracts
import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import fixed_kernel_calibration_panel_20260926 as panel
import fixed_kernel_direction_calibration_common_20260926 as c

p = c.p
SCRIPT = "trusted_data_synthesis/scripts/prepare_direction_calibration_panel_20260926.py"
TICKERS = "https://www.sec.gov/files/company_tickers.json"
SALT = "direction_calibration_new_sources_20260926.v1:"
USER_AGENT = "Data-Synthesis academic research https://github.com/haoyueliuzhao/Data-Synthesis"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # A redirect would make an additional, unregistered HTTP request.


def save_response(key, attempt, payload):
    path = folder() / "raw_attempts" / key / f"{attempt:04d}.bin"
    c.b.durable.atomic_bytes(path, payload, immutable=True)
    return dict(path=str(path), bytes=len(payload), sha256=p.sha(payload))


def folder():
    return c.RAW / "panel_sources"


def register(root):
    path = folder() / "acquisition_plan.json"
    if path.exists():
        return read_plan(root)
    parent = c.read_protocol(root)
    source_root = panel._source_root(root)
    old_path = source_root / panel.HISTORICAL_METADATA
    metadata = p.read_json(old_path)
    excluded = sorted({row["source_cluster"] for row in metadata["rows"]})
    p.require(len(excluded) == 100, "calibration_sources.original100_CIKs")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    names = sorted(set((SCRIPT, *panel.CODE_PATHS)))
    sources = {}
    for name in names:
        payload = (root / name).read_bytes()
        p.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "calibration_sources.committed_builder_and_collector",
        )
        sources[name] = p.sha(payload)
    plan = p.record(
        "direction_calibration_source_acquisition_plan",
        parent_reliability_protocol_id=parent["id"],
        code_commit=head,
        sources=sources,
        official_directory_url=TICKERS,
        companyfacts_url_template="https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        excluded_CIKs=excluded,
        excluded_historical_tickers=sorted(panel.HISTORICAL_TICKERS),
        original_source_metadata_sha256=p.sha(old_path),
        candidate_count=64,
        selection_rule=dict(
            directory="one frozen official SEC ticker/CIK response",
            deduplication="per CIK, lexicographically first eligible ticker",
            source_split="original fixed salt dev only",
            hash_salt=SALT,
            sort="SHA256(salt + cik:10digits), then CIK",
            old_score_inputs=0,
        ),
        roster_before_companyfacts=True,
        all_sources_sealed_before_task_enumeration=True,
        source_replacement=False,
        max_HTTP_requests=195,
        max_attempts_per_asset=3,
        minimum_request_interval_seconds=0.5,
        maximum_response_bytes=64 * 2**20,
        on_HTTP403_or_429="stop globally; no alternate identity, host or proxy",
        retry_only="network errors or HTTP5xx, at most 3 attempts",
        user_agent=USER_AGENT,
        new_Probe_materials=0,
        new_feedback_sampling=0,
        new_model_calls=0,
        target_groups=dict.fromkeys(panel.GROUPS, 60),
        original_years=[2010, 2025],
        panel_rule_id=panel.policy()["id"],
        insufficient_sources_or_tasks="STOP_WITH_EVIDENCE_NO_EXPANSION",
        at=p.now(),
    )
    c.write(path, plan)
    return plan


def read_plan(root):
    plan = p.checked(
        p.read_json(folder() / "acquisition_plan.json"),
        "direction_calibration_source_acquisition_plan",
    )
    p.require(
        plan["parent_reliability_protocol_id"] == c.read_protocol(root)["id"],
        "calibration_sources.registered_parent",
    )
    for name, expected in plan["sources"].items():
        p.require(p.sha(root / name) == expected, "calibration_sources.frozen_code:" + name)
    return plan


def choose(directory, plan):
    by_cik = {}
    excluded = set(plan["excluded_CIKs"])
    tickers = set(plan["excluded_historical_tickers"])
    p.require(isinstance(directory, dict), "calibration_sources.official_directory_object")
    excluded.update(
        "cik:" + str(int(row["cik_str"])).zfill(10)
        for row in directory.values()
        if str(row["ticker"]).upper() in tickers
    )
    for value in directory.values():
        cik = str(int(value["cik_str"])).zfill(10)
        ticker = str(value["ticker"]).upper()
        title = str(value["title"])
        p.require(
            len(cik) == 10 and int(cik) > 0 and ticker and title,
            "calibration_sources.entity_metadata",
        )
        if (
            "cik:" + cik in excluded
            or ticker in tickers
            or panel.source_split("cik:" + cik) != "dev"
        ):
            continue
        row = dict(cik=cik, ticker=ticker, title=title)
        if cik not in by_cik or ticker < by_cik[cik]["ticker"]:
            by_cik[cik] = row
    rows = sorted(
        by_cik.values(),
        key=lambda row: (
            p.sha(plan["selection_rule"]["hash_salt"] + "cik:" + row["cik"]),
            row["cik"],
        ),
    )
    p.require(
        len(rows) >= plan["candidate_count"], "calibration_sources.insufficient_new_metadata_CIKs"
    )
    return rows[: plan["candidate_count"]], len(rows)


def get_asset(plan, key, url):
    destination = folder() / "snapshots" / (key + ".json")
    receipt_path = folder() / "receipts" / (key + ".json")
    if receipt_path.exists():
        receipt = p.checked(p.read_json(receipt_path), "calibration_source_HTTP_receipt")
        p.require(
            receipt["plan_id"] == plan["id"]
            and receipt["url"] == url
            and p.sha(destination) == receipt["sha256"]
            and destination.stat().st_size == receipt["bytes"],
            "calibration_sources.reuse_exact_snapshot",
        )
        return destination, receipt
    # A previous access denial is never retried under a new identity or path.
    p.require(not (folder() / "access_blocked.json").exists(), "calibration_sources.access_blocked")
    p.require(
        not (folder() / "terminal_failures" / (key + ".json")).exists(),
        "calibration_sources.asset_terminal_failure",
    )
    intents = folder() / "network" / key
    used = max((int(f.stem) for f in intents.glob("*.json")), default=0)
    for attempt in range(used + 1, plan["max_attempts_per_asset"] + 1):
        with c.locked(folder() / "network.lock"):
            state_path = folder() / "network/state.json"
            state = (
                p.read_json(state_path) if state_path.exists() else dict(requests=0, last_started=0)
            )
            p.require(
                state["requests"] < plan["max_HTTP_requests"],
                "calibration_sources.HTTP_budget_exhausted",
            )
            time.sleep(
                max(
                    0,
                    plan["minimum_request_interval_seconds"]
                    - (time.time() - state["last_started"]),
                )
            )
            state.update(requests=state["requests"] + 1, last_started=time.time())
            c.write(state_path, state, immutable=False)
            c.write(
                intents / f"{attempt:04d}.json",
                dict(plan_id=plan["id"], url=url, attempt=attempt, at=p.now()),
            )
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": plan["user_agent"],
                    "Accept-Encoding": "identity",
                    "Accept": "application/json",
                },
            )
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
                p.require(response.geturl() == url, "calibration_sources.no_unregistered_redirect")
                payload = response.read(plan["maximum_response_bytes"] + 1)
                raw_reference = save_response(key, attempt, payload)
                p.require(
                    len(payload) <= plan["maximum_response_bytes"],
                    "calibration_sources.fixed_response_byte_limit",
                )
                headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() in ("content-type", "etag", "last-modified", "date")
                }
                status = response.status
            value = json.loads(payload)
            if key != "directory":
                p.require(
                    str(int(value["cik"])).zfill(10) == key
                    and isinstance(value.get("facts"), dict),
                    "calibration_sources.original_companyfacts_CIK",
                )
            else:
                p.require(
                    isinstance(value, dict) and value, "calibration_sources.nonempty_directory"
                )
            # Bytes first, receipt second. Orphan successful bytes are preserved, never overwritten.
            if destination.exists():
                destination.rename(
                    destination.with_name(
                        destination.stem + f"_uncommitted_before_attempt{attempt}.json"
                    )
                )
            c.b.durable.atomic_bytes(destination, payload, immutable=True)
            receipt = p.record(
                "calibration_source_HTTP_receipt",
                plan_id=plan["id"],
                url=url,
                status=status,
                headers=headers,
                sha256=p.sha(payload),
                bytes=len(payload),
                attempt=attempt,
                raw_response=raw_reference,
                at=p.now(),
            )
            c.write(receipt_path, receipt)
            c.emit(
                dict(
                    event="calibration_source_saved",
                    asset=key,
                    bytes=len(payload),
                    request_number=state["requests"],
                )
            )
            return destination, receipt
        except urllib.error.HTTPError as error:
            denied = error.code in (403, 429)
            info = dict(url=url, status=error.code, error=str(error), attempt=attempt, at=p.now())
            if denied:
                c.write(folder() / "access_blocked.json", info)
            payload = error.read(plan["maximum_response_bytes"] + 1) if error.fp else b""
            raw_reference = save_response(key, attempt, payload)
            info["raw_response"] = raw_reference
            c.write(folder() / "failures" / key / f"{attempt:04d}.json", info)
            if denied:
                c.write(folder() / "access_blocked.json", info, immutable=False)
                raise
            if not 500 <= error.code < 600:
                c.write(folder() / "terminal_failures" / (key + ".json"), info)
                raise
        except (ValueError, KeyError, TypeError) as error:
            c.write(
                folder() / "terminal_failures" / (key + ".json"),
                dict(url=url, error=repr(error), attempt=attempt, at=p.now()),
            )
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            c.write(
                folder() / "failures" / key / f"{attempt:04d}.json",
                dict(url=url, error=repr(error), attempt=attempt, at=p.now()),
            )
        if attempt < plan["max_attempts_per_asset"]:
            time.sleep(5 * attempt)
    raise RuntimeError("calibration_sources.asset_attempt_cap:" + key)


def acquire(root):
    plan = read_plan(root)
    with c.locked(folder() / "acquisition.lock", blocking=False):
        path, receipt = get_asset(plan, "directory", plan["official_directory_url"])
        roster_path = folder() / "roster.json"
        if roster_path.exists():
            roster = p.checked(p.read_json(roster_path), "calibration_new_CIK_roster")
            p.require(
                roster["plan_id"] == plan["id"] and roster["directory_sha256"] == receipt["sha256"],
                "calibration_sources.fixed_roster",
            )
        else:
            rows, eligible = choose(p.read_json(path), plan)
            roster = p.record(
                "calibration_new_CIK_roster",
                plan_id=plan["id"],
                directory_sha256=receipt["sha256"],
                eligible_metadata_CIKs=eligible,
                sources=rows,
                selection_rule=plan["selection_rule"],
                no_companyfacts_values_read_before_roster=True,
                at=p.now(),
            )
            c.write(roster_path, roster)
        sources = []
        for row in roster["sources"]:
            path, receipt = get_asset(
                plan, row["cik"], plan["companyfacts_url_template"].format(cik=row["cik"])
            )
            sources.append(
                dict(
                    **row,
                    path=str(path),
                    sha256=receipt["sha256"],
                    bytes=receipt["bytes"],
                    receipt_id=receipt["id"],
                )
            )
        output = folder() / "source_registration.json"
        if output.exists():
            previous = p.checked(p.read_json(output), "calibration_source_registration")
            p.require(
                previous["acquisition_plan_id"] == plan["id"]
                and previous["roster_id"] == roster["id"]
                and previous["sources"] == sources,
                "calibration_sources.same_source_registration",
            )
            return previous
        value = p.record(
            "calibration_source_registration",
            acquisition_plan_id=plan["id"],
            roster_id=roster["id"],
            code_commit=plan["code_commit"],
            sources=sources,
            selection_rule=plan["selection_rule"],
            registered_at=p.now(),
        )
        c.write(output, value)
        return value


def run(root):
    try:
        sources = acquire(root)
        output = c.RAW / "calibration_panel"
        admission = output / "admission.json"
        if admission.exists():
            value = p.read_json(admission)
        else:
            result = panel.build(root, sources, output)
            value = result["admission"]
        completion = folder() / "completion.json"
        if completion.exists():
            previous = p.read_json(completion)
            p.require(
                previous["source_registration_id"] == sources["id"]
                and previous["panel_admission_id"] == value["id"]
                and previous["passed"] == value["passed"],
                "calibration_sources.same_completed_admission",
            )
        else:
            c.write(
                completion,
                dict(
                    source_registration_id=sources["id"],
                    panel_admission_id=value["id"],
                    passed=value["passed"],
                    new_model_calls=0,
                    at=p.now(),
                ),
            )
        c.emit(
            dict(event="new_calibration_panel_admission", passed=value["passed"], id=value["id"])
        )
        return 0 if value["passed"] else 1
    except Exception as error:
        c.write(
            folder() / "needs_attention.json", dict(error=repr(error), at=p.now()), immutable=False
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", required=True, choices=("register", "run"))
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "register":
        value = register(root)
        c.emit(
            dict(
                event="new_calibration_source_plan_registered",
                id=value["id"],
                max_CIKs=64,
                max_HTTP_requests=195,
            )
        )
    else:
        raise SystemExit(run(root))
